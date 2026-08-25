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

from apps.api.app.ai.errors import AIProviderConfigurationError, AIProviderError
from apps.api.app.ai.hermes_endpoint import normalize_hermes_base_url
from apps.api.app.ai.providers import _SYSTEM_PROMPT, _build_prompt, _classify_http_error

logger = logging.getLogger(__name__)


class HermesAgentProvider:
    """Production adapter for a private Hermes Agent gateway."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        timeout_seconds: float = 120.0,
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
        if maximum_latency_ms is not None and maximum_latency_ms > 0:
            timeout_seconds = min(self._timeout, maximum_latency_ms / 1000)
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
            raise AIProviderError("provider", "Hermes agent request timed out") from None
        except httpx.ConnectError:
            raise AIProviderError(
                "provider", "Could not connect to the Hermes agent runtime"
            ) from None
        except httpx.RequestError as exc:
            raise AIProviderError("provider", "Hermes agent request failed") from exc

        latency_ms = int((monotonic() - started) * 1000)
        if response.status_code != 200:
            category, safe_message = _classify_http_error(response.status_code)
            logger.warning(
                "Hermes agent returned non-200",
                extra={
                    "event_name": "ai.hermes.http_error",
                    "status_code": response.status_code,
                    "task_key": task_key,
                },
            )
            raise AIProviderError(category, safe_message)

        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            raise AIProviderError(
                "provider", "Hermes agent returned an unparseable response"
            ) from None
        if not isinstance(body, dict):
            raise AIProviderError("provider", "Hermes agent returned an invalid response object")
        if self._api_key in json.dumps(body, sort_keys=True):
            raise AIProviderError("provider", "Hermes agent returned unsafe output")

        choices = body.get("choices", [])
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise AIProviderError("provider", "Hermes agent returned no completion choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise AIProviderError("provider", "Hermes agent returned an invalid completion")
        content_text = str(message.get("content", "")).strip()
        if not content_text:
            raise AIProviderError("provider", "Hermes agent returned empty content")

        if content_text.startswith("```json") and content_text.endswith("```"):
            content_text = content_text[7:-3].strip()
        elif content_text.startswith("```") and content_text.endswith("```"):
            content_text = content_text[3:-3].strip()

        try:
            parsed = json.loads(content_text)
        except (json.JSONDecodeError, ValueError):
            raise AIProviderError(
                "provider", "Hermes agent returned content that is not valid JSON"
            ) from None
        if not isinstance(parsed, dict):
            raise AIProviderError(
                "provider", "Hermes agent returned content that is not a JSON object"
            )

        draft = str(parsed.get("draft", "")).strip()
        if not draft:
            raise AIProviderError("provider", "Hermes agent returned no draft field")

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
