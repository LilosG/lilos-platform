from decimal import Decimal

import pytest

from apps.api.app.insights.service import (
    aggregate,
    anomaly,
    observation,
    percent_change,
    snapshot_hash,
)


def test_missing_zero_partial_and_suppressed_are_distinct() -> None:
    assert observation(None, "missing") != observation(Decimal(0), "zero")
    assert observation(Decimal(2), "partial")["state"] == "partial"
    with pytest.raises(ValueError):
        observation(None, "zero")


def test_definition_driven_aggregation_fails_closed() -> None:
    assert aggregate([Decimal(2), Decimal(3)], "sum") == 5
    assert aggregate(
        [Decimal(2), Decimal(4)], "weighted_average", weights=[Decimal(1), Decimal(3)]
    ) == Decimal("3.5")
    with pytest.raises(ValueError):
        aggregate([Decimal(2)], "average")
    with pytest.raises(ValueError):
        aggregate([], "sum")


def test_zero_denominator_does_not_invent_percentage() -> None:
    assert percent_change(Decimal(4), Decimal(0)) is None


def test_report_snapshot_is_reproducible_and_anomaly_requires_data() -> None:
    payload = {"metric": "seo.clicks", "value": None, "state": "missing", "version": 1}
    assert snapshot_hash(payload) == snapshot_hash(dict(reversed(list(payload.items()))))
    assert anomaly([Decimal(1)] * 6, Decimal(10))["reason"] == "insufficient_data"
