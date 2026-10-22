"""Hermes Agent provider for the governed LILOs AI Gateway.

Hermes is treated as an agent runtime rather than a raw model endpoint. LILOs
continues to own tenant scope, approved business-fact grounding, cost/latency
bounds, approvals, audit, and all external provider mutations. The adapter
uses Hermes' authenticated OpenAI-compatible API server over Render's private
network.
"""

from __future__ import annotations

import json
import logging
from hashlib import sha256
from time import monotonic
from typing import Any
from uuid import UUID

import httpx

from apps.api.app.ai.completion_text import DraftExtractionError, extract_draft
from apps.api.app.ai.errors import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderFailureCode,
)
from apps.api.app.ai.hermes_endpoint import normalize_hermes_base_url
from apps.api.app.ai.providers import (
    _SYSTEM_PROMPT,
    _build_prompt,
    completion_content,
    completion_finish_reason,
    http_failure,
)

logger = logging.getLogger(__name__)


class HermesAgentProvider:
    """Production adapter for a private Hermes Agent gateway."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        timeout_seconds: float = 120.0,
        max_timeout_seconds: float = 300.0,
        max_output_tokens: int = 2_000,
        model: str = "hermes-agent",
    ) -> None:
        if not api_key or not api_key.strip():
            raise AIProviderConfigurationError("Hermes API key is required when ai_provider=hermes")
        try:
            normalized_base_url = normalize_hermes_base_url(base_url)
        except ValueError as exc:
            raise AIProviderConfigurationError(
                "Hermes base URL is invalid when ai_provider=hermes"
            ) from exc

        self._api_key = api_key.strip()
        self._base_url = normalized_base_url
        self._timeout = timeout_seconds
        self._max_timeout = max_timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._model = model.strip() or "hermes-agent"

    async def generate(
        self,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        task_key: str,
        input_document: dict[str, Any],
        maximum_tokens: int,
        maximum_latency_ms: int | None = None,
    ) -> dict[str, Any]:
        """Execute a governed LILOs task through the Hermes agent gateway."""
        prompt = _build_prompt(task_key, input_document)
        max_tokens = min(maximum_tokens, self._max_output_tokens)
        # A per-request limit is authoritative, bounded only by the ceiling;
        # the default timeout applies when the request gives none.
        if maximum_latency_ms is not None and maximum_latency_ms > 0:
            timeout_seconds = min(self._max_timeout, maximum_latency_ms / 1000)
        else:
            timeout_seconds = self._timeout

        scope_material = f"{organization_id}:{location_id or 'organization'}:{task_key}"
        session_key = f"lilos:{sha256(scope_material.encode()).hexdigest()[:32]}"

        started = monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "X-Hermes-Session-Key": session_key,
                    },
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": 0.4,
                    },
                )
        except httpx.TimeoutException:
            raise AIProviderError(
                "provider",
                "Hermes agent request timed out",
                code=AIProviderFailureCode.TIMEOUT,
                elapsed_ms=int((monotonic() - started) * 1000),
            ) from None
        except httpx.ConnectError:
            raise AIProviderError(
                "provider",
                "Could not connect to the Hermes agent runtime",
                code=AIProviderFailureCode.CONNECTION,
                elapsed_ms=int((monotonic() - started) * 1000),
            ) from None
        except httpx.RequestError as exc:
            raise AIProviderError(
                "provider",
                "Hermes agent request failed",
                code=AIProviderFailureCode.CONNECTION,
                elapsed_ms=int((monotonic() - started) * 1000),
            ) from exc

        latency_ms = int((monotonic() - started) * 1000)
        if response.status_code != 200:
            raise http_failure(response.status_code, elapsed_ms=latency_ms)

        def failure(message: str, code: AIProviderFailureCode, **measured: Any) -> AIProviderError:
            return AIProviderError(
                "provider",
                message,
                code=code,
                http_status=response.status_code,
                elapsed_ms=latency_ms,
                **measured,
            )

        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            raise failure(
                "Hermes agent returned an unparseable response",
                AIProviderFailureCode.UNPARSEABLE_RESPONSE,
            ) from None
        if not isinstance(body, dict):
            raise failure(
                "Hermes agent returned an invalid response object",
                AIProviderFailureCode.UNPARSEABLE_RESPONSE,
            )
        if self._api_key in json.dumps(body, sort_keys=True):
            raise failure(
                "Hermes agent returned unsafe output", AIProviderFailureCode.MALFORMED_OUTPUT
            )

        choices = body.get("choices", [])
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise failure(
                "Hermes agent returned no completion choices", AIProviderFailureCode.NO_CHOICES
            )
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise failure(
                "Hermes agent returned an invalid completion", AIProviderFailureCode.NO_CHOICES
            )
        finish_reason = completion_finish_reason(choices[0])
        reported = (
            (body.get("usage") or {}).get("completion_tokens")
            if isinstance(body.get("usage") or {}, dict)
            else None
        )
        measured: dict[str, Any] = {
            "finish_reason": finish_reason,
            "output_tokens": reported if isinstance(reported, int) else None,
        }
        if finish_reason == "length":
            raise failure(
                "Hermes agent stopped before finishing (output token limit reached)",
                AIProviderFailureCode.OUTPUT_TRUNCATED,
                **measured,
            )
        content_text = completion_content(message)
        # The agent runtime cannot be sent response_format, so it answers in
        # prose as often as in JSON. Both are accepted; see completion_text.
        try:
            draft = extract_draft(content_text, subject="Hermes agent")
        except DraftExtractionError as error:
            raise failure(error.reason, error.code, **measured) from None

        usage = body.get("usage", {}) or {}
        if not isinstance(usage, dict):
            usage = {}
        return {
            "provider": "hermes",
            "model": str(body.get("model", self._model)),
            "draft": draft,
            "requires_human_review": True,
            "usage": {
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
            "latency_ms": latency_ms,
            "cost_microunits": None,
            "request_id": str(body.get("id", "")) or None,
        }
