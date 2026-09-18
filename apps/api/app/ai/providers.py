"""Production AI provider adapters implementing the AIProvider protocol."""

from __future__ import annotations

import json
import logging
import re
from time import monotonic
from typing import Any
from uuid import UUID

import httpx

from apps.api.app.ai.completion_text import (
    DraftExtractionError,
    extract_draft,
    strip_code_fence,
)
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

_ARTICLE_CONTENT_TYPES = frozenset(
    {
        "article",
        "blog",
        "blog_post",
        "blog-post",
        "guide",
        "local_guide",
        "local-guide",
        "page",
        "landing",
        "landing_page",
        "landing-page",
    }
)
_LONGFORM_CONTENT_TYPES = frozenset(
    {"article", "blog", "blog_post", "blog-post", "guide", "local_guide", "local-guide"}
)
_PAGE_CONTENT_TYPES = frozenset({"page", "landing", "landing_page", "landing-page"})
_ARTICLE_MINIMUM_RELEVANT_H2S = 3
_ARTICLE_MINIMUM_FAQ_ANSWER_WORDS = 18
_ARTICLE_MINIMUM_SECTION_WORDS = 90
_ARTICLE_MAXIMUM_THIN_SECTIONS = 1
_TOPIC_OVERLAP_THRESHOLD = 0.75
_TOPIC_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "best",
        "by",
        "for",
        "from",
        "guide",
        "how",
        "in",
        "near",
        "of",
        "on",
        "the",
        "to",
        "with",
    }
)


def _classify_http_error(status_code: int) -> tuple[str, str]:
    """Return (category, safe_message) for an HTTP status code."""
    if status_code in _HTTP_ERROR_CATEGORIES:
        return _HTTP_ERROR_CATEGORIES[status_code]
    if 400 <= status_code < 500:
        return ("permanent", f"AI provider rejected the request (HTTP {status_code})")
    if 500 <= status_code < 600:
        return ("provider", f"AI provider encountered an error (HTTP {status_code})")
    return ("provider", f"AI provider returned unexpected status {status_code}")


def _is_article_content_type(content_type: object) -> bool:
    return str(content_type or "").strip().casefold() in _ARTICLE_CONTENT_TYPES


def _article_quality_profile(content_type: object) -> dict[str, int]:
    normalized = str(content_type or "").strip().casefold()
    if normalized in _LONGFORM_CONTENT_TYPES:
        return {
            "minimum_words": 1_400,
            "target_minimum_words": 1_700,
            "target_maximum_words": 2_300,
            "minimum_h2s": 7,
            "minimum_internal_links": 4,
            "minimum_faqs": 4,
        }
    if normalized in _PAGE_CONTENT_TYPES:
        return {
            "minimum_words": 1_100,
            "target_minimum_words": 1_350,
            "target_maximum_words": 1_800,
            "minimum_h2s": 6,
            "minimum_internal_links": 3,
            "minimum_faqs": 3,
        }
    return {
        "minimum_words": 900,
        "target_minimum_words": 1_100,
        "target_maximum_words": 1_500,
        "minimum_h2s": 6,
        "minimum_internal_links": 3,
        "minimum_faqs": 3,
    }


def _topic_tokens(value: object) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", str(value or "").casefold())
    return {token for token in tokens if len(token) > 2 and token not in _TOPIC_STOPWORDS}


def _find_existing_topic_overlap(input_document: dict[str, Any]) -> str | None:
    """Return the URL of a strongly overlapping indexed page, when one exists."""
    if not _is_article_content_type(input_document.get("content_type")):
        return None
    target_tokens = _topic_tokens(input_document.get("content_title"))
    if len(target_tokens) < 3:
        return None
    knowledge = input_document.get("knowledge")
    if not isinstance(knowledge, dict):
        return None
    pages = knowledge.get("website_knowledge")
    if not isinstance(pages, list):
        return None
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_title = page.get("title") or page.get("h1")
        page_tokens = _topic_tokens(page_title)
        if len(page_tokens) < 3:
            continue
        shared = target_tokens & page_tokens
        containment = len(shared) / min(len(target_tokens), len(page_tokens))
        if len(shared) >= 4 and containment >= _TOPIC_OVERLAP_THRESHOLD:
            return str(page.get("url") or page_title or "existing website page")
    return None


def _content_knowledge_for_prompt(raw: object) -> dict[str, object]:
    """Bound website grounding so article prompts stay useful instead of enormous."""
    if not isinstance(raw, dict):
        return {}
    result: dict[str, object] = {}
    for key in ("identity", "gbp_knowledge"):
        value = raw.get(key)
        if isinstance(value, list) and value:
            result[key] = value[:10]
    website = raw.get("website_knowledge")
    if isinstance(website, list):
        pages: list[dict[str, object]] = []
        for raw_page in website[:10]:
            if not isinstance(raw_page, dict):
                continue
            page: dict[str, object] = {}
            for key in ("url", "title", "h1", "meta_description"):
                value = raw_page.get(key)
                if value:
                    page[key] = value
            body_text = raw_page.get("body_text")
            if body_text:
                page["body_excerpt"] = str(body_text)[:1800]
            if page:
                pages.append(page)
        if pages:
            result["website_knowledge"] = pages
    return result


def _extract_content_payload(content_text: str) -> dict[str, Any]:
    """Parse the full structured Content response instead of discarding SEO fields."""
    text = strip_code_fence(content_text)
    if not text:
        raise DraftExtractionError("AI provider returned empty content")
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        raise DraftExtractionError(
            "AI provider returned Content output that is not valid JSON"
        ) from None
    if not isinstance(parsed, dict):
        raise DraftExtractionError("AI provider returned Content output that is not a JSON object")
    draft = str(parsed.get("draft") or "").strip()
    if not draft:
        raise DraftExtractionError("AI provider returned no draft field")
    parsed["draft"] = draft
    return parsed


def _validate_article_payload(payload: dict[str, Any], input_document: dict[str, Any]) -> list[str]:
    """Deterministic quality floor for AI-generated local SEO content."""
    if not _is_article_content_type(input_document.get("content_type")):
        return []

    profile = _article_quality_profile(input_document.get("content_type"))
    draft = str(payload.get("draft") or "")
    errors: list[str] = []
    words = re.findall(r"\b[\w'-]+\b", draft)
    if len(words) < profile["minimum_words"]:
        errors.append("article_too_thin")

    if re.search(r"(?m)^#\s+\S", draft):
        errors.append("article_body_h1_not_allowed")

    h2_matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", draft))
    h2s = [match.group(1) for match in h2_matches]
    if len(h2s) < profile["minimum_h2s"]:
        errors.append("article_heading_depth_missing")
    if len({heading.casefold().strip() for heading in h2s}) != len(h2s):
        errors.append("article_duplicate_headings")

    if h2_matches:
        section_word_counts: list[int] = []
        for index, match in enumerate(h2_matches):
            start = match.end()
            end = h2_matches[index + 1].start() if index + 1 < len(h2_matches) else len(draft)
            section = draft[start:end]
            section_word_counts.append(len(re.findall(r"\b[\w'-]+\b", section)))
        thin_sections = sum(count < _ARTICLE_MINIMUM_SECTION_WORDS for count in section_word_counts)
        if thin_sections > _ARTICLE_MAXIMUM_THIN_SECTIONS:
            errors.append("article_sections_too_thin")

    internal_links = re.findall(r"\[[^\]]+\]\((/[^)\s]+)\)", draft)
    unique_links = set(internal_links)
    knowledge = _content_knowledge_for_prompt(input_document.get("knowledge"))
    website_pages = knowledge.get("website_knowledge")
    allowed_urls = (
        {
            str(page.get("url"))
            for page in website_pages
            if isinstance(page, dict) and page.get("url")
        }
        if isinstance(website_pages, list)
        else set()
    )
    required_links = min(profile["minimum_internal_links"], len(allowed_urls))
    if required_links and len(unique_links & allowed_urls) < required_links:
        errors.append("article_internal_links_missing")
    if allowed_urls and any(link not in allowed_urls for link in unique_links):
        errors.append("article_internal_link_unverified")

    paragraphs = [
        " ".join(paragraph.split()).casefold()
        for paragraph in re.split(r"\n\s*\n", draft)
        if len(re.findall(r"\b[\w'-]+\b", paragraph)) >= 25
        and not paragraph.lstrip().startswith("#")
    ]
    if len(paragraphs) != len(set(paragraphs)):
        errors.append("article_repeated_paragraphs")

    faqs = payload.get("faqs")
    valid_faqs = (
        [
            faq
            for faq in faqs
            if isinstance(faq, dict)
            and str(faq.get("question") or "").strip()
            and len(re.findall(r"\b[\w'-]+\b", str(faq.get("answer") or "")))
            >= _ARTICLE_MINIMUM_FAQ_ANSWER_WORDS
        ]
        if isinstance(faqs, list)
        else []
    )
    if len(valid_faqs) < profile["minimum_faqs"]:
        errors.append("article_faq_depth_missing")

    if not str(payload.get("meta_description") or "").strip():
        errors.append("article_meta_description_missing")
    if not str(payload.get("seo_title") or "").strip():
        errors.append("article_seo_title_missing")

    title_tokens = _topic_tokens(input_document.get("content_title"))
    if title_tokens and h2s:
        relevant_h2s = sum(bool(title_tokens & _topic_tokens(heading)) for heading in h2s)
        if relevant_h2s < min(_ARTICLE_MINIMUM_RELEVANT_H2S, len(h2s)):
            errors.append("article_search_intent_headings_missing")
    return sorted(set(errors))


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
        if task_key == "content.draft_revision":
            overlap = _find_existing_topic_overlap(input_document)
            if overlap:
                raise AIProviderError(
                    "permanent",
                    f"Content topic substantially overlaps an existing website page: {overlap}",
                )

        model = self._default_model
        prompt = _build_prompt(task_key, input_document)
        max_tokens = min(maximum_tokens, self._max_output_tokens)

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

        choices = body.get("choices", [])
        if not choices:
            raise AIProviderError("provider", "AI provider returned no completion choices")
        message = choices[0].get("message", {})
        content_text = str(message.get("content", ""))

        content_fields: dict[str, Any] = {}
        try:
            if task_key == "content.draft_revision":
                content_payload = _extract_content_payload(content_text)
                draft = str(content_payload["draft"])
                quality_errors = _validate_article_payload(content_payload, input_document)
                if quality_errors:
                    raise AIProviderError(
                        "permanent",
                        "AI provider returned Content output below the publishing quality floor: "
                        + ", ".join(quality_errors),
                    )
                for key in (
                    "meta_description",
                    "seo_title",
                    "faqs",
                    "related_services",
                    "service_areas",
                    "tags",
                    "category",
                ):
                    if key in content_payload:
                        content_fields[key] = content_payload[key]
            else:
                draft = extract_draft(content_text, subject="AI provider")
        except DraftExtractionError as error:
            raise AIProviderError("provider", error.reason) from None

        if task_key == "gbp.generate_post" and _looks_like_review_response(draft):
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

        usage = body.get("usage", {}) or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")
        provider_cost_usd = usage.get("cost")
        cost_microunits: int | None = None
        if isinstance(provider_cost_usd, (int, float)) and provider_cost_usd >= 0:
            cost_microunits = int(round(float(provider_cost_usd) * 1_000_000))

        provider_model = str(body.get("model", model))
        request_id = str(body.get("id", ""))

        result: dict[str, Any] = {
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
        result.update(content_fields)
        return result


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a governed content assistant for the LILOs platform. "
    "You produce grounded, policy-compliant content for human review. "
    "Always return a JSON object that follows the task-specific output contract "
    "and includes a 'draft' key. Never include secrets, credentials, or personally "
    "identifiable information in your output. "
    "Only use approved business facts and source-backed knowledge provided in the prompt. "
    "Never invent claims, capabilities, guarantees, business details, locations, pricing, "
    "hours, menu items, credentials, or service areas that are not present in the supplied sources."
)


def _format_governed_facts(facts: list[dict[str, object]]) -> str:
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
    audience = str(input_document.get("audience", "general"))
    intent = str(input_document.get("intent", "inform"))
    rating = input_document.get("rating")
    manual_fallback = str(input_document.get("manual_fallback", ""))
    content_title = str(input_document.get("content_title", ""))
    content_type = str(input_document.get("content_type", ""))
    governed_facts = input_document.get("governed_facts", [])
    validation_requirements = input_document.get("validation_requirements")
    required_claims = input_document.get("required_claims")
    required_local_references = input_document.get("required_local_references")
    source_evidence_references = input_document.get("source_evidence_references")

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
                f"\nRECENT POSTS TO AVOID REPEATING:\n{json.dumps(recent_posts, default=str)}"
            )
        if selected_target_url:
            parts.append(f"\nCTA TARGET (do not paste into body): {selected_target_url}")
        if instructions:
            parts.append(f"\nTASK-SPECIFIC INSTRUCTIONS:\n{instructions}")
        parts.append("\nReturn ONLY a JSON object with the key 'draft'.")
        return "\n".join(parts)

    if task_key == "content.draft_revision":
        facts_section = _format_governed_facts(governed_facts) if governed_facts else ""
        knowledge = _content_knowledge_for_prompt(input_document.get("knowledge"))
        parts = [
            (
                "Write a source-backed website content draft for the supplied audience "
                "and search intent."
            ),
            (
                "The goal is a useful, authoritative page for a real local customer, "
                "not generic SEO filler."
            ),
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
        if knowledge:
            parts.append(
                "\nSOURCE-BACKED WEBSITE AND LOCAL KNOWLEDGE. Use these pages for factual context "
                "and for natural internal links. Never invent a URL that is not present here:\n"
                + json.dumps(knowledge, default=str)
            )

        if _is_article_content_type(content_type):
            profile = _article_quality_profile(content_type)
            if validation_requirements:
                parts.append(
                    "\nBRIEF VALIDATION REQUIREMENTS:\n"
                    + json.dumps(validation_requirements, default=str)
                )
            if required_claims:
                parts.append("\nREQUIRED CLAIMS:\n" + json.dumps(required_claims, default=str))
            if required_local_references:
                parts.append(
                    "\nREQUIRED LOCAL REFERENCES:\n"
                    + json.dumps(required_local_references, default=str)
                )
            if source_evidence_references:
                parts.append(
                    "\nSOURCE EVIDENCE REFERENCES:\n"
                    + json.dumps(source_evidence_references, default=str)
                )
            parts.extend(
                [
                    "\nARTICLE QUALITY CONTRACT:",
                    (
                        f"- Target {profile['target_minimum_words']:,}–"
                        f"{profile['target_maximum_words']:,} substantive words when the supplied "
                        "evidence supports that depth. Never pad to hit a number; every paragraph "
                        "must answer a real question, support a decision, explain a distinction, "
                        "or add source-backed local/business context."
                    ),
                    (
                        "- Do NOT put an H1 in the markdown body. The site template renders "
                        "the frontmatter title as the single H1."
                    ),
                    (
                        f"- Use at least {profile['minimum_h2s']} descriptive H2 sections. Build "
                        "a complete outline before drafting; each major section must cover a "
                        "distinct subtopic and contain substantive explanatory copy, not a stub."
                    ),
                    (
                        "- Make headings specific to the primary search intent, secondary customer "
                        "questions, and local/business context. Avoid generic headings such as "
                        "'About Us', 'Overview', 'Why Choose Us', or 'Conclusion'."
                    ),
                    (
                        "- Answer the primary intent near the beginning, then cover the practical "
                        "follow-up questions a customer would need before acting: what to expect, "
                        "options or tradeoffs, timing/planning, location/context, fit, and the next "
                        "step when those details are supported by the supplied evidence."
                    ),
                    (
                        "- Synthesize the supplied first-party sources instead of paraphrasing one "
                        "page repeatedly. Use specific details where supported and avoid claims "
                        "that the evidence does not establish."
                    ),
                    (
                        f"- Include natural internal markdown links to up to "
                        f"{profile['minimum_internal_links']} relevant first-party URLs present in "
                        "SOURCE-BACKED WEBSITE AND LOCAL KNOWLEDGE. Never invent an internal URL."
                    ),
                    (
                        "- Use neighborhood, city, street, landmark, menu, service, hours, and "
                        "other local details only when they are present in approved facts or "
                        "source-backed knowledge."
                    ),
                    (
                        "- Avoid keyword stuffing, repetitive business descriptions, templated "
                        "filler, unsupported superlatives, and repeated conclusions. Vary sentence "
                        "structure and make the prose read like an expert human editor wrote it."
                    ),
                    (
                        "- End with a useful, source-supported next step when the intent is "
                        "commercial or transactional. Do not invent offers, availability, pricing, "
                        "capacity, guarantees, or reservation terms."
                    ),
                    (
                        f"- Return {profile['minimum_faqs']} to six FAQs that answer genuine "
                        "customer questions not already answered verbatim in the article. Each "
                        "answer should be at least two useful sentences when the evidence permits."
                    ),
                    (
                        "\nReturn ONLY one JSON object with these keys: `draft`, "
                        "`meta_description`, `seo_title`, `faqs`, `related_services`, "
                        "`service_areas`, `tags`, and `category`. `meta_description` must be "
                        "one useful sentence under 155 characters. `seo_title` must be under 60 "
                        "characters. Do not include frontmatter inside `draft`."
                    ),
                ]
            )
        else:
            parts.append(
                "\nProduce a well-structured professional draft using only the supplied facts "
                "and knowledge. Return ONLY one JSON object with the keys `draft`, "
                "`meta_description`, `seo_title`, `faqs`, `related_services`, `service_areas`, "
                "`tags`, and `category`."
            )
        return "\n".join(parts)

    if task_key == "reviews.response_draft":
        review = input_document.get("review")
        review_document = review if isinstance(review, dict) else {}
        review_title = str(review_document.get("title") or "").strip()
        review_body = str(review_document.get("body") or "").strip()
        review_rating = review_document.get("rating", rating)
        rating_text = (
            f"Rating: {review_rating}/5" if review_rating is not None else "Rating: not provided"
        )
        facts_section = _format_governed_facts(governed_facts) if governed_facts else ""
        parts = [
            "Write a public response to the customer's actual review.",
            "The review text is the primary source. Respond to what the customer actually said, "
            "not to a generic business profile or SEO description.",
            "Keep the response natural, specific, concise, and human. Two to four sentences is "
            "usually enough unless the review genuinely requires more context.",
            "Vary the opening naturally. Do not default to canned phrases such as 'Thank you for "
            "sharing your experience' or 'We take all feedback seriously' when a more direct "
            "response fits the review.",
            "Do not recite business categories, service lists, positioning language, or keyword "
            "phrases merely because they appear in approved facts. Use an approved fact only when "
            "it materially helps answer a point raised in the review.",
            "Never invent facts, offers, compensation, contact details, policies, outcomes, or "
            "promises. For a negative review, acknowledge the concern without admitting unverified "
            "wrongdoing or promising a remedy that is not supported by the supplied facts.",
            rating_text,
        ]
        if review_title:
            parts.append(f"\nREVIEW TITLE:\n{review_title}")
        if review_body:
            parts.append(f"\nREVIEW BODY:\n{review_body}")
        if not review_title and not review_body:
            parts.append(
                "\nREVIEW TEXT: No written review text was provided; respond to the rating only."
            )
        if facts_section:
            parts.append(
                "\nOPTIONAL APPROVED BUSINESS FACTS "
                "(use only when directly relevant to the customer's feedback; do not force them "
                "into the response):"
                f"\n{facts_section}"
            )
        if manual_fallback:
            parts.append(f"\nFALLBACK TONE REFERENCE ONLY:\n{manual_fallback}")
        parts.append("\nReturn ONLY a JSON object with the key 'draft'.")
        return "\n".join(parts)

    return (
        f"Task: {task_key}\n\n"
        f"Input: {json.dumps(input_document, default=str)}\n\n"
        f"Return ONLY a JSON object with the key 'draft'."
    )
