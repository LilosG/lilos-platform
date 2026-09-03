"""Central model routing for governed LILOs AI work.

Model selection is configuration, not product logic. Both direct AI Gateway
requests and native Hermes agent runs resolve through this module so a task
cannot silently use a different model depending on execution path.
"""

from __future__ import annotations

from apps.api.app.config import Settings


def resolve_task_model(
    task_key: str | None,
    settings: Settings,
    *,
    fallback: str | None = None,
) -> str | None:
    """Resolve one task's configured model using a single precedence rule.

    Precedence is explicit per-task override, configured platform default,
    then the caller-provided runtime fallback. Empty model values are rejected
    by ``Settings`` at the field level; overrides are normalized here because
    they originate inside a JSON string.
    """
    overrides = settings.ai_task_model_map()
    if task_key and task_key in overrides:
        model = overrides[task_key].strip()
        if not model:
            raise ValueError(f"AI model override for '{task_key}' must not be empty")
        return model

    if settings.ai_default_model:
        model = settings.ai_default_model.strip()
        if model:
            return model

    if fallback:
        model = fallback.strip()
        if model:
            return model
    return None


def is_dynamic_openrouter_route(model: str | None) -> bool:
    """Return whether a model delegates model choice back to OpenRouter."""
    return model is None or model.strip().lower() == "openrouter/auto"
