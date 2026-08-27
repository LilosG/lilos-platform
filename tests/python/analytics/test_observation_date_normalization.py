"""GA4 date dimensions must reach the frontend as ISO dates.

The Analytics Data API returns its `date` dimension in basic format, YYYYMMDD.
Python's date.fromisoformat accepts that, so ingestion never complained and the
raw value was stored and served through to the reporting series. JavaScript's
`new Date("20260813T00:00:00Z")` is invalid, so every GA4 chart axis label
rendered "Invalid Date" -- visible on the live Insights page -- while Search
Console, which returns extended format, rendered correctly.
"""

from apps.api.app.products.analytics.service import normalize_observation_date


def test_basic_format_becomes_iso() -> None:
    assert normalize_observation_date("20260813") == "2026-08-13"


def test_iso_is_left_alone() -> None:
    assert normalize_observation_date("2026-08-13") == "2026-08-13"


def test_unrecognised_values_are_returned_unchanged() -> None:
    """A bad value must surface as itself, never as a plausible wrong date."""
    for value in ("not-a-date", "2026-08", "202608134"):
        assert normalize_observation_date(value) == value


def test_none_becomes_empty_string() -> None:
    assert normalize_observation_date(None) == ""


def test_whitespace_is_trimmed() -> None:
    assert normalize_observation_date("  20260813  ") == "2026-08-13"


def test_output_is_parseable_by_javascript_date_construction() -> None:
    """The exact string the chart builds must be a valid ISO instant."""
    from datetime import datetime

    normalized = normalize_observation_date("20260813")

    # Mirrors the frontend's `new Date(`${date}T00:00:00Z`)`.
    assert datetime.fromisoformat(f"{normalized}T00:00:00+00:00").year == 2026
