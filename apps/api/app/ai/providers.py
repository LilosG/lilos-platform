"""Production AI provider adapters implementing the AIProvider protocol."""

from __future__ import annotations

import json
import logging
from time import monotonic
from typing import Any
from uuid import UUID

import httpx

from apps.api.app.ai.completion_text import DraftExtractionError, extract_draft
from apps.api.app.ai.errors import AIProviderConfigurationError, AIProviderError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safe error classification — never includes provider secrets in messages
# ---------------------------------------------------------------------------

_HTTP_ERROR_CATEGORIES: dict[int, tuple[str, str]] = {
    401: ("configuration", "AI provider authentication failed — check the API key"),
    403: ("configuration", "AI provider access denied — verify account permissions"),
    429: ("provider", "AI provider rate limit exceeded — retry after a short delay"),
    502: ("provider", "AI provider returned an upstream error"),
    503: ("provider", "AI provider is temporarily unavailable"),
    504: ("provider", "AI provider request timed out"),
}


def _classify_http_error(status_code: int) -> tuple[str, str]:
    """Return (category, safe_message) for an HTTP status code."""
    if status_code in _HTTP_ERROR_CATEGORIES:
        return _HTTP_ERROR_CATEGORIES[status_code]
    if 400 <= status_code < 500:
        return ("permanent", f"AI provider rejected the request (HTTP {status_code})")
    if 500 <= status_code < 600:
        return ("provider", f"AI provider encountered an error (HTTP {status_code})")
    return ("provider", f"AI provider returned unexpected status {status_code}")


# ---------------------------------------------------------------------------
# OpenRouter provider
# ---------------------------------------------------------------------------


class OpenRouterProvider:
    """Production AI provider adapter for OpenRouter.

    Implements the ``AIProvider`` protocol defined in ``apps.api.app.ai.gateway``.
    Constructed with a validated API key and optional base URL override; never
    logs or returns the key.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 60.0,
        max_output_tokens: int = 2_000,
        default_model: str | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise AIProviderConfigurationError(
                "OpenRouter API key is required when ai_provider=openrouter"
            )
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._default_model = default_model or "openrouter/auto"

    async def generate(
        self,
        *,
        organization_id: UUID | None = None,
        location_id: UUID | None = None,
        task_key: str,
        input_document: dict[str, Any],
        maximum_tokens: int,
        maximum_latency_ms: int | None = None,
    ) -> dict[str, Any]:
        """Call OpenRouter chat completions and return a governed output dict.

        The returned dict always includes ``provider``, ``model``, ``draft``,
        ``requires_human_review``, ``usage``, ``latency_ms``, and
        ``cost_microunits`` (actual provider-reported USD cost when available).
        """
        del organization_id, location_id
        model = self._default_model
        prompt = _build_prompt(task_key, input_document)
        max_tokens = min(maximum_tokens, self._max_output_tokens)

        # Enforce the task's maximum latency bound (when provided) against the
        # provider's configured ceiling.
        if maximum_latency_ms is not None and maximum_latency_ms > 0:
            timeout_seconds = min(self._timeout, maximum_latency_ms / 1000)
        else:
            timeout_seconds = self._timeout

        started = monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://lilos.ai",
                        "X-Title": "LILOs Platform",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": 0.7,
                        "response_format": {"type": "json_object"},
                        # Ask OpenRouter to include provider-accounted usage and
                        # USD cost in the response. This avoids maintaining a
                        # stale pricing table inside LILOs.
                        "usage": {"include": True},
                    },
                )
        except httpx.TimeoutException:
            raise AIProviderError(
                "provider", "AI provider request timed out — the service may be overloaded"
            ) from None
        except httpx.ConnectError:
            raise AIProviderError(
                "provider", "Could not connect to the AI provider — check network configuration"
            ) from None
        except httpx.RequestError as exc:
            raise AIProviderError(
                "provider", "AI provider request failed — the service may be unavailable"
            ) from exc

        latency_ms = int((monotonic() - started) * 1000)

        if response.status_code != 200:
            category, safe_message = _classify_http_error(response.status_code)
            logger.warning(
                "AI provider returned non-200",
                extra={
                    "event_name": "ai.provider.http_error",
                    "provider": "openrouter",
                    "status_code": response.status_code,
                    "task_key": task_key,
                },
            )
            raise AIProviderError(category, safe_message)

        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            raise AIProviderError(
                "provider", "AI provider returned an unparseable response"
            ) from None

        # Extract the assistant message content
        choices = body.get("choices", [])
        if not choices:
            raise AIProviderError("provider", "AI provider returned no completion choices")
        message = choices[0].get("message", {})
        content_text = str(message.get("content", ""))
        # response_format=json_object makes structured output the norm here, but
        # a model that answers in prose anyway has still answered. Shared with
        # the agent-runtime provider so one rule governs both.
        try:
            draft = extract_draft(content_text, subject="AI provider")
        except DraftExtractionError as error:
            raise AIProviderError("provider", error.reason) from None

        if task_key == "gbp.generate_post" and _looks_like_review_response(draft):
            # A customer review may ground a Local Post, but the Local Post is
            # public marketing content for prospective customers — never a reply
            # addressed back to the reviewer. If the model drifts into review-
            # response voice, use the already-governed manual fallback rather
            # than persist a bad proposal for an operator to discover later.
            fallback = " ".join(str(input_document.get("manual_fallback") or "").split())
            if not fallback:
                raise AIProviderError(
                    "provider", "AI provider returned review-response copy for a GBP Local Post"
                )
            logger.warning(
                "Rejected review-response voice from GBP Local Post generation",
                extra={
                    "event_name": "ai.gbp_post.review_response_rejected",
                    "task_key": task_key,
                },
            )
            draft = fallback[:1200].rstrip()

        # Usage metadata. OpenRouter returns request cost in USD as usage.cost.
        usage = body.get("usage", {}) or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")
        provider_cost_usd = usage.get("cost")
        cost_microunits: int | None = None
        if isinstance(provider_cost_usd, (int, float)) and provider_cost_usd >= 0:
            # LILOs monetary microunits are millionths of one USD.
            cost_microunits = int(round(float(provider_cost_usd) * 1_000_000))

        provider_model = str(body.get("model", model))
        request_id = str(body.get("id", ""))

        return {
            "provider": "openrouter",
            "model": provider_model,
            "draft": draft,
            "requires_human_review": True,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
            "latency_ms": latency_ms,
            "cost_microunits": cost_microunits,
            "request_id": request_id,
        }


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a governed content assistant for the LILOs platform. "
    "You produce grounded, policy-compliant content for human review. "
    "Always return a JSON object with a single key 'draft' containing the "
    "generated text. Never include secrets, credentials, or personally "
    "identifiable information in your output. "
    "Only use approved business facts provided in the prompt. "
    "Never invent claims, capabilities, guarantees, or business details "
    "that are not present in the approved facts."
)


def _format_governed_facts(facts: list[dict[str, object]]) -> str:
    """Format resolved governed facts for inclusion in the AI prompt."""
    if not facts:
        return ""
    lines: list[str] = []
    for f in facts:
        fact_key = str(f.get("fact_key", "unknown"))
        value = f.get("value")
        authority = str(f.get("authority", "unknown"))
        lines.append(f"- {fact_key}: {value} (authority: {authority})")
    return "\n".join(lines)


def _looks_like_review_response(draft: str) -> bool:
    """Detect direct-to-reviewer reply language that is invalid for a Local Post."""
    normalized = " ".join(draft.casefold().split())
    if not normalized:
        return False
    direct_openers = (
        "thank you",
        "thanks for",
        "we're so glad",
        "we are so glad",
        "we're thrilled",
        "we are thrilled",
        "we appreciate your",
        "we appreciate the feedback",
        "so glad you",
        "glad to hear you",
        "happy to hear you",
    )
    if normalized.startswith(direct_openers):
        return True
    response_signals = (
        "thank you for the 5-star",
        "thank you for your review",
        "thanks for your review",
        "appreciate your review",
        "glad you enjoyed",
        "happy you enjoyed",
        "hope to see you again",
        "hope to welcome you back",
        "welcome you back soon",
        "look forward to welcoming you back",
    )
    return any(signal in normalized for signal in response_signals)


def _build_prompt(task_key: str, input_document: dict[str, Any]) -> str:
    """Build a task-specific prompt from the input document."""
    audience = str(input_document.get("audience", "general"))
    intent = str(input_document.get("intent", "inform"))
    rating = input_document.get("rating")
    manual_fallback = str(input_document.get("manual_fallback", ""))
    content_title = str(input_document.get("content_title", ""))
    content_type = str(input_document.get("content_type", ""))
    governed_facts = input_document.get("governed_facts", [])

    if task_key == "gbp.generate_post":
        facts_section = _format_governed_facts(governed_facts) if governed_facts else ""
        source_type = str(input_document.get("source_type", ""))
        source_review = input_document.get("source_review")
        source_service = input_document.get("source_service")
        knowledge = input_document.get("knowledge")
        profile = input_document.get("current_gbp_profile")
        recent_posts = input_document.get("recent_posts_to_avoid_repeating")
        selected_target_url = str(input_document.get("selected_target_url", ""))
        instructions = str(input_document.get("instructions", ""))
        parts = [
            "Write a Google Business Profile Local Post for prospective customers.",
            "This is public marketing content, NOT a response to a customer review.",
            "Never address the reviewer directly. Never thank the reviewer, say 'your review', "
            "say that 'we are glad/thrilled/happy you...' or invite that reviewer to return.",
            "Never mention a star rating or write in review-reply voice.",
            "If a customer review is supplied, use it only as third-person evidence of a real "
            "customer experience. Faithfully paraphrase the relevant experience without "
            "identifying the reviewer or inventing details.",
            "Write for someone deciding whether to visit, book, call, or learn more about the "
            "business. Keep the post natural, useful, and under 1,200 characters.",
            "Do not place the target URL in the body; LILOs attaches it as the CTA.",
            f"Audience: {audience}",
            f"Intent: {intent}",
            f"Content title: {content_title}",
            f"Source type: {source_type}",
        ]
        if facts_section:
            parts.append(
                "\nAPPROVED BUSINESS FACTS "
                "(authoritative — do not invent anything not listed here):"
                f"\n{facts_section}"
            )
        if source_review is not None:
            parts.append(f"\nSOURCE CUSTOMER REVIEW:\n{json.dumps(source_review, default=str)}")
        if source_service is not None:
            parts.append(f"\nSOURCE SERVICE:\n{json.dumps(source_service, default=str)}")
        if profile:
            parts.append(f"\nCURRENT GBP PROFILE:\n{json.dumps(profile, default=str)}")
        if knowledge:
            parts.append(f"\nCLIENT-OWNED KNOWLEDGE:\n{json.dumps(knowledge, default=str)}")
        if recent_posts:
            parts.append(
                "\nRECENT POSTS TO AVOID REPEATING:\n"
                f"{json.dumps(recent_posts, default=str)}"
            )
        if selected_target_url:
            parts.append(f"\nCTA TARGET (do not paste into body): {selected_target_url}")
        if instructions:
            parts.append(f"\nTASK-SPECIFIC INSTRUCTIONS:\n{instructions}")
        parts.append("\nReturn ONLY a JSON object with the key 'draft'.")
        return "\n".join(parts)
    if task_key == "content.draft_revision":
        facts_section = _format_governed_facts(governed_facts) if governed_facts else ""
        parts = [
            "Write a content draft for the following audience, intent, and approved business facts."
        ]
        if content_title:
            parts.append(f"\nTitle: {content_title}")
        if content_type:
            parts.append(f"Type: {content_type}")
        parts.append(f"\nAudience: {audience}")
        parts.append(f"Intent: {intent}")
        if facts_section:
            parts.append(
                "\nAPPROVED BUSINESS FACTS "
                "(authoritative — do not invent anything not listed here):"
                f"\n{facts_section}"
            )
        parts.append(
            "\nProduce a well-structured, professional draft. "
            "Return ONLY a JSON object with the key 'draft'."
        )
        return "\n".join(parts)
    if task_key == "reviews.response_draft":
        rating_text = f"Rating: {rating}/5" if rating is not None else "Rating: not provided"
        facts_section = _format_governed_facts(governed_facts) if governed_facts else ""
        parts = [
            "Draft a professional, grounded review response.",
            "",
            rating_text,
            f"Fallback tone: {manual_fallback}",
        ]
        if facts_section:
            parts.append(
                "\nAPPROVED BUSINESS FACTS "
                "(authoritative — do not invent anything not listed here):"
                f"\n{facts_section}"
            )
        parts.append(
            "\nWrite a response that is empathetic, professional, and appropriate "
            "for the rating level. Use the approved business facts above to ground "
            "your response in real business context. "
            "Return ONLY a JSON object with the key 'draft'."
        )
        return "\n".join(parts)
    # Generic fallback for any task
    return (
        f"Task: {task_key}\n\n"
        f"Input: {json.dumps(input_document, default=str)}\n\n"
        f"Return ONLY a JSON object with the key 'draft'."
    )
