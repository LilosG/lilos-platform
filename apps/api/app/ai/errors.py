"""Provider-neutral AI error categories for safe operator and client visibility."""

from __future__ import annotations


class AIProviderError(Exception):
    """A governed AI provider failure with a safe, non-secret-bearing message."""

    def __init__(self, category: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.category = category
        self.safe_message = safe_message


class AIProviderConfigurationError(AIProviderError):
    """The AI provider is not correctly configured for this environment."""

    def __init__(self, safe_message: str) -> None:
        super().__init__("configuration", safe_message)
