"""Reading a draft out of a model completion, structured or not.

Both providers asked the model for ``{"draft": "..."}`` and treated anything
else as a failure. That is fine when the provider can enforce the shape —
OpenRouter is sent ``response_format: json_object`` — and wrong when it cannot:
the Hermes agent runtime answers in prose, so a perfectly usable review reply
was discarded with "returned content that is not valid JSON" and the operator
got nothing.

A draft is prose. The JSON envelope is our convenience, not a property of the
answer, so an unstructured answer is salvaged rather than rejected. Every draft
still requires human approval before it can be published, so a salvaged draft
is reviewed exactly like a structured one.

What is NOT salvaged is a structured answer that arrived broken — content that
opens as a JSON object or array and fails to parse is truncated or malformed,
and its fragments are not a draft. That case still fails loudly.
"""

import json


class DraftExtractionError(Exception):
    """Raised with a safe, specific reason when no draft can be read."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def strip_code_fence(text: str) -> str:
    """Remove a surrounding markdown code fence, if present."""
    trimmed = text.strip()
    if trimmed.startswith("```json") and trimmed.endswith("```"):
        return trimmed[7:-3].strip()
    if trimmed.startswith("```") and trimmed.endswith("```"):
        return trimmed[3:-3].strip()
    return trimmed


def extract_draft(content_text: str, *, subject: str) -> str:
    """Return the draft text from a completion body.

    ``subject`` names the provider in any raised reason, e.g. "Hermes agent".
    """
    text = strip_code_fence(content_text)
    if not text:
        raise DraftExtractionError(f"{subject} returned empty content")

    try:
        parsed: object = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Structured intent that failed to parse is broken, not prose: a
        # truncated object would otherwise be handed to an operator as a draft
        # with its opening brace still attached.
        if text.startswith("{") or text.startswith("["):
            raise DraftExtractionError(
                f"{subject} returned content that is not valid JSON"
            ) from None
        return text

    if isinstance(parsed, dict):
        draft = str(parsed.get("draft", "")).strip()
        if not draft:
            raise DraftExtractionError(f"{subject} returned no draft field")
        return draft

    if isinstance(parsed, str):
        # A bare JSON string is still an answer.
        draft = parsed.strip()
        if not draft:
            raise DraftExtractionError(f"{subject} returned empty content")
        return draft

    raise DraftExtractionError(f"{subject} returned content that is not a JSON object")
