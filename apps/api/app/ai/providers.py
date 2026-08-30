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
        ``cost_microunits`` (estimated from provider-reported cost when
        available, otherwise None).
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

        # Usage metadata
        usage = body.get("usage", {}) or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")

        # Cost — OpenRouter returns cost in the response body (cents)
        provider_cost_cents = body.get("cost")
        cost_microunits: int | None = None
        if isinstance(provider_cost_cents, (int, float)):
            # Convert cents to microunits (1 cent = 10,000 microunits)
            cost_microunits = int(round(float(provider_cost_cents) * 10_000))

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


def _build_prompt(task_key: str, input_document: dict[str, Any]) -> str:
    """Build a task-specific prompt from the input document."""
    audience = str(input_document.get("audience", "general"))
    intent = str(input_document.get("intent", "inform"))
    rating = input_document.get("rating")
    manual_fallback = str(input_document.get("manual_fallback", ""))
    content_title = str(input_document.get("content_title", ""))
    content_type = str(input_document.get("content_type", ""))
    governed_facts = input_document.get("governed_facts", [])

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
