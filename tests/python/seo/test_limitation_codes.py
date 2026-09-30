"""LIMITATION_COPY must cover every SEOLimitationCode exhaustively.

A code without copy would surface a KeyError the first time a governed
decision was refused for that reason, instead of failing at review time.
"""

from apps.api.app.products.seo.decision import SEOEvidenceInvalidError
from apps.api.app.products.seo.limitation_codes import LIMITATION_COPY, SEOLimitationCode


def test_every_limitation_code_has_copy() -> None:
    assert set(LIMITATION_COPY) == set(SEOLimitationCode)


def test_every_copy_entry_is_a_nonempty_sentence() -> None:
    for code, copy in LIMITATION_COPY.items():
        assert copy.strip(), f"{code} has blank copy"
        assert copy.endswith("."), f"{code} copy should read as a full sentence"


def test_error_carries_both_the_code_and_its_registered_copy() -> None:
    error = SEOEvidenceInvalidError(SEOLimitationCode.PAGE_OUT_OF_SCOPE)
    assert error.limitation_code == "PAGE_OUT_OF_SCOPE"
    assert error.public_message == LIMITATION_COPY[SEOLimitationCode.PAGE_OUT_OF_SCOPE]
    assert str(error) == error.public_message
