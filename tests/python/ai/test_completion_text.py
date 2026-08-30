"""Reading a draft out of a completion, structured or not.

The defect these pin: a review reply that arrived as prose was discarded with
"returned content that is not valid JSON", so the operator got an error instead
of the perfectly usable draft the model had written.
"""

import pytest

from apps.api.app.ai.completion_text import (
    DraftExtractionError,
    extract_draft,
    strip_code_fence,
)


class TestStructuredAnswers:
    def test_reads_the_draft_field(self) -> None:
        assert extract_draft('{"draft": "Thank you for visiting."}', subject="X") == (
            "Thank you for visiting."
        )

    def test_reads_through_a_json_code_fence(self) -> None:
        body = '```json\n{"draft": "Thanks!"}\n```'
        assert extract_draft(body, subject="X") == "Thanks!"

    def test_reads_through_a_bare_code_fence(self) -> None:
        assert extract_draft('```\n{"draft": "Thanks!"}\n```', subject="X") == "Thanks!"

    def test_a_bare_json_string_is_still_an_answer(self) -> None:
        assert extract_draft('"Thank you for the kind words."', subject="X") == (
            "Thank you for the kind words."
        )

    def test_an_object_without_a_draft_field_is_refused(self) -> None:
        # A structured answer that deliberately carries something else is not a
        # draft, and its JSON must never be shown to an operator as prose.
        with pytest.raises(DraftExtractionError, match="no draft field"):
            extract_draft('{"refusal": "cannot comply"}', subject="X")

    def test_a_json_array_is_refused(self) -> None:
        with pytest.raises(DraftExtractionError, match="not a JSON object"):
            extract_draft("[1, 2, 3]", subject="X")


class TestProseAnswers:
    def test_prose_is_used_as_the_draft(self) -> None:
        # The whole point: the agent runtime cannot be sent response_format, so
        # it answers in prose, and that answer is usable.
        prose = (
            "Thank you for the detailed feedback. We're sorry the music and "
            "service fell short, and we've shared this with our team."
        )
        assert extract_draft(prose, subject="Hermes agent") == prose

    def test_prose_inside_a_code_fence_is_used(self) -> None:
        assert extract_draft("```\nThanks for coming in.\n```", subject="X") == (
            "Thanks for coming in."
        )

    def test_surrounding_whitespace_is_trimmed(self) -> None:
        assert extract_draft("   Thanks!  \n", subject="X") == "Thanks!"

    def test_prose_that_merely_mentions_json_is_not_treated_as_broken(self) -> None:
        text = "Thanks for your review of our JSON parsing workshop."
        assert extract_draft(text, subject="X") == text


class TestBrokenStructuredAnswers:
    @pytest.mark.parametrize(
        "body",
        [
            '{"draft": "Thank you for vis',
            '{"draft":',
            "[{'draft': 'x'}",
        ],
    )
    def test_a_truncated_object_fails_rather_than_leaking_fragments(self, body: str) -> None:
        # Truncation (a token ceiling, a dropped connection) is a real failure.
        # Salvaging it would hand an operator a draft with a brace attached.
        with pytest.raises(DraftExtractionError, match="not valid JSON"):
            extract_draft(body, subject="X")

    def test_the_subject_names_the_provider_in_the_reason(self) -> None:
        with pytest.raises(DraftExtractionError, match="Hermes agent"):
            extract_draft('{"draft": ', subject="Hermes agent")


class TestEmptyAnswers:
    @pytest.mark.parametrize("body", ["", "   ", "\n\n", "```\n```", '""'])
    def test_nothing_at_all_is_refused(self, body: str) -> None:
        with pytest.raises(DraftExtractionError, match="empty content"):
            extract_draft(body, subject="X")


class TestCodeFence:
    def test_leaves_unfenced_text_alone(self) -> None:
        assert strip_code_fence("plain text") == "plain text"

    def test_does_not_strip_a_half_open_fence(self) -> None:
        assert strip_code_fence("```json\nstill open") == "```json\nstill open"
