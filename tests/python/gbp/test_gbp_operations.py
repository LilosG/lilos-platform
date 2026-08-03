from datetime import date, time

import pytest

from apps.api.app.products.gbp.operations import (
    Capability,
    completeness,
    conflicts,
    require_capability,
    validate_hours,
)


def test_capability_is_explicit_and_fails_closed() -> None:
    values = {"posts": Capability("posts", True, False, "read only")}
    assert require_capability(values, "posts", write=False).readable
    with pytest.raises(ValueError):
        require_capability(values, "posts", write=True)
    with pytest.raises(ValueError):
        require_capability(values, "q_and_a", write=False)


def test_hours_reject_overlap_and_guesses() -> None:
    day = date(2026, 12, 25)
    with pytest.raises(ValueError):
        validate_hours([(day, time(9), time(13)), (day, time(12), time(17))])
    validate_hours([(day, time(9), time(12)), (day, time(13), time(17))])


def test_completeness_excludes_unsupported_and_is_not_ranking() -> None:
    result = completeness({"title", "hours"}, {"title": "Known", "q_and_a": None})
    assert result["unknown"] == ["hours"] and result["ranking_score"] is None


def test_material_conflicts_are_not_silently_resolved() -> None:
    assert conflicts({"hours": "9-5"}, {"hours": "8-5"}, {"hours": "9-4"})[0]["field"] == "hours"
