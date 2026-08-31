"""Recognising that two organization names are the same client.

The defect: only the slug was unique, so "Cococabana" and "cococabana" became
two separate clients with no warning — a permanent duplicate in every switcher
and client list, with nothing to say which one held the real work.
"""

import pytest

from apps.api.app.organizations.naming import normalize_organization_name


class TestNamesThatMeanTheSameClient:
    @pytest.mark.parametrize(
        ("left", "right"),
        [
            ("Cococabana", "cococabana"),
            ("Coco Maya", "coco maya"),
            ("Coco  Maya", "Coco Maya"),
            ("  Coco Maya  ", "Coco Maya"),
            ("Coco-Maya", "Coco Maya"),
            ("Coco Maya.", "Coco Maya"),
            ("O'Brien Plumbing", "OBrien Plumbing"),
            ("O\u2019Brien Plumbing", "O'Brien Plumbing"),
            ("Wheyland Electric, Inc.", "Wheyland Electric Inc"),
        ],
    )
    def test_they_normalize_together(self, left: str, right: str) -> None:
        assert normalize_organization_name(left) == normalize_organization_name(right)


class TestNamesThatAreDifferentClients:
    @pytest.mark.parametrize(
        ("left", "right"),
        [
            ("Coco Maya", "Coco Maya Two"),
            ("Cococabana", "Coco Cabana"),
            ("Wheyland Electric", "Wheyland Plumbing"),
        ],
    )
    def test_they_stay_apart(self, left: str, right: str) -> None:
        # Collapsing too aggressively would refuse to create a real client.
        assert normalize_organization_name(left) != normalize_organization_name(right)


def test_unicode_composition_does_not_split_one_name_in_two() -> None:
    # "Café" typed two ways is one client.
    assert normalize_organization_name("Café Roma") == normalize_organization_name("Café Roma")


def test_an_all_punctuation_name_collapses_to_nothing_rather_than_raising() -> None:
    assert normalize_organization_name("---") == ""
