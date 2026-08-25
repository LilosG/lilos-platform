"""Hermes custom plugin for the sanctioned LILOs tool plane."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from gateway.session_context import get_session_env
from tools.registry import tool_error, tool_result


def _object(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


STRING = {"type": "string"}
STRINGS = {"type": "array", "items": STRING, "maxItems": 100}
OBJECT = {"type": "object"}
OBJECTS = {"type": "array", "items": OBJECT, "maxItems": 100}

SCHEMAS = {
    "read_client_business_facts": _object({}),
    "read_website_knowledge": _object({"query": STRING}),
    "read_gbp_state": _object({}),
    "read_gbp_recent_posts": _object({"limit": {"type": "integer", "minimum": 1, "maximum": 50}}),
    "read_gsc_evidence": _object({"days": {"type": "integer", "enum": [7, 28, 90]}}),
    "read_ga4_evidence": _object({"days": {"type": "integer", "enum": [7, 28, 90]}}),
    "read_reviews_state": _object({"limit": {"type": "integer", "minimum": 1, "maximum": 50}}),
    "read_content_inventory": _object({"limit": {"type": "integer", "minimum": 1, "maximum": 50}}),
    "read_cross_product_summary": _object({}),
    "run_site_crawl": _object({}),
    "analyze_seo_opportunities": _object(
        {"limit": {"type": "integer", "minimum": 1, "maximum": 50}}
    ),
    "create_seo_recommendation_proposal": _object(
        {
            "opportunity_id": STRING,
            "proposed_action": STRING,
            "evidence_references": STRINGS,
            "expected_result_hypothesis": STRING,
            "risk": {"type": "string", "enum": ["low", "medium", "high"]},
            "effort": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        [
            "opportunity_id",
            "proposed_action",
            "evidence_references",
            "expected_result_hypothesis",
            "risk",
            "effort",
        ],
    ),
    "create_content_proposal": _object(
        {"content_opportunity_id": STRING, "content_type": STRING, "title": STRING, "slug": STRING},
        ["content_opportunity_id", "content_type", "title", "slug"],
    ),
    "create_content_brief": _object(
        {
            "content_item_id": STRING,
            "audience": STRING,
            "intent": STRING,
            "target_reference": STRING,
            "approved_fact_revision_ids": STRINGS,
            "required_claims": STRINGS,
            "prohibited_claims": STRINGS,
            "required_local_references": STRINGS,
            "source_evidence_references": STRINGS,
        },
        [
            "content_item_id",
            "audience",
            "intent",
            "target_reference",
            "approved_fact_revision_ids",
            "source_evidence_references",
        ],
    ),
    "generate_content_draft_proposal": _object(
        {
            "content_item_id": STRING,
            "content_brief_id": STRING,
            "body": {"type": "string", "minLength": 1, "maxLength": 200000},
            "frontmatter": OBJECT,
            "approved_fact_revision_ids": STRINGS,
            "source_evidence_references": STRINGS,
        },
        [
            "content_item_id",
            "content_brief_id",
            "body",
            "frontmatter",
            "approved_fact_revision_ids",
            "source_evidence_references",
        ],
    ),
    "generate_gbp_post_proposal": _object(
        {
            "post_type": {"type": "string", "enum": ["standard", "event", "offer", "alert"]},
            "content": STRING,
            "call_to_action": OBJECT,
            "source_evidence_references": STRINGS,
        },
        ["post_type", "content", "source_evidence_references"],
    ),
    "create_gbp_optimization_proposal": _object(
        {
            "capability_key": STRING,
            "field_changes": OBJECTS,
            "evidence_references": STRINGS,
            "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        ["capability_key", "field_changes", "evidence_references", "risk"],
    ),
    "draft_review_response_proposal": _object(
        {"review_id": STRING, "response_text": STRING, "approved_fact_revision_ids": STRINGS},
        ["review_id", "response_text", "approved_fact_revision_ids"],
    ),
    "inspect_workflow": _object({}),
    "submit_for_approval": _object({"proposal_reference": STRING}, ["proposal_reference"]),
}

DESCRIPTIONS = {
    "read_client_business_facts": (
        "Read current approved business facts with authority and source references."
    ),
    "read_website_knowledge": "Read bounded source-backed website and identity knowledge.",
    "read_gbp_state": "Read the current GBP snapshot and freshness; never writes Google.",
    "read_gbp_recent_posts": "Read provider posts and LILOs post revisions to avoid repetition.",
    "read_gsc_evidence": "Read persisted Search Console evidence with period and quality state.",
    "read_ga4_evidence": "Read persisted GA4 evidence with period and quality state.",
    "read_reviews_state": "Read reviews, deterministic risk state, and latest text.",
    "read_content_inventory": "Read content items and evidence-backed opportunities.",
    "read_cross_product_summary": "Read the persisted cross-product operational summary.",
    "run_site_crawl": "Request the canonical LILOs crawl workflow.",
    "analyze_seo_opportunities": "Read opportunities produced by deterministic SEO detectors.",
    "create_seo_recommendation_proposal": "Create an approval-waiting SEO recommendation.",
    "create_content_proposal": "Convert an accepted opportunity into a governed Content item.",
    "create_content_brief": "Create a grounded Content brief from approved facts and evidence.",
    "generate_content_draft_proposal": (
        "Create an editorial-review Content revision grounded in a ready brief."
    ),
    "generate_gbp_post_proposal": "Create an approval-waiting GBP post revision; never publishes.",
    "create_gbp_optimization_proposal": (
        "Create an approval-waiting GBP change-set; never edits Google."
    ),
    "draft_review_response_proposal": "Draft a review response when deterministic risk permits.",
    "inspect_workflow": "Inspect the owning LILOs workflow.",
    "submit_for_approval": "Submit this run's proposal to the canonical LILOs approval queue.",
}


def _available() -> bool:
    return bool(os.getenv("LILOS_TOOL_BASE_URL") and os.getenv("LILOS_TOOL_API_KEY"))


def _safe_http_error(exc: HTTPError) -> str:
    code = f"HTTP_{exc.code}"
    message = "LILOs rejected the tool request"
    try:
        payload = json.loads(exc.read(8_192))
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            raw_code = error.get("code")
            raw_message = error.get("message")
            if isinstance(raw_code, str) and raw_code:
                code = raw_code[:96]
            if isinstance(raw_message, str) and raw_message:
                message = raw_message[:500]
    except (ValueError, OSError):
        pass
    return f"LILOs tool error [{code}]: {message}"


def _invoke(tool_name: str, args: dict) -> str:
    session_id = get_session_env("HERMES_SESSION_CHAT_ID", "").strip()
    if not session_id:
        return tool_error("LILOs rejected the tool call: no bound run session")
    base_url = os.getenv("LILOS_TOOL_BASE_URL", "").strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        base_url = f"http://{base_url}"
    body = json.dumps({"arguments": args}, separators=(",", ":")).encode()
    request = Request(
        f"{base_url}/api/internal/hermes/tools/{tool_name}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {os.getenv('LILOS_TOOL_API_KEY', '')}",
            "Content-Type": "application/json",
            "X-LILOS-Hermes-Session": session_id,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read(65_536))
        return tool_result(payload.get("data", {}))
    except HTTPError as exc:
        return tool_error(_safe_http_error(exc))
    except (URLError, TimeoutError, ValueError):
        return tool_error("LILOs tool plane is unavailable")


def register(ctx) -> None:
    for name, parameters in SCHEMAS.items():

        def handler(args: dict, _name: str = name, **kwargs) -> str:
            del kwargs
            return _invoke(_name, args)

        ctx.register_tool(
            name=name,
            toolset="lilos",
            schema={"name": name, "description": DESCRIPTIONS[name], "parameters": parameters},
            handler=handler,
            check_fn=_available,
            requires_env=["LILOS_TOOL_BASE_URL", "LILOS_TOOL_API_KEY"],
            description=DESCRIPTIONS[name],
            emoji="🔒",
        )
