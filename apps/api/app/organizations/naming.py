"""Comparing organization names the way a person reads them.

Only the slug was ever unique, so "Cococabana" and "cococabana" were accepted as
two separate clients with no warning — a permanent duplicate in every switcher
and client list, with nothing to say which one held the real work.

Names are deliberately still not unique in the database: two real clients may
share one. This is the comparison used to warn about a collision at the moment
it is created, when it is cheap to resolve.
"""

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
# Apostrophes are dropped rather than spaced, so "O'Brien" and "OBrien" are one
# client. Spacing them would split the name into "o brien" and separate it from
# the spelling without the mark.
_ELIDED = re.compile(r"['\u2018\u2019\u02bc]")
# Remaining punctuation becomes a space, so "Coco-Maya" and "Coco Maya" meet.
_INSIGNIFICANT = re.compile(r"[^\w\s]", flags=re.UNICODE)


def normalize_organization_name(name: str) -> str:
    """Return a comparison key for an organization name.

    Case, surrounding and repeated whitespace, punctuation, and Unicode
    composition differences are all discarded, because none of them
    distinguishes one client from another to the person typing the name.
    """
    decomposed = unicodedata.normalize("NFKC", name)
    without_marks = _ELIDED.sub("", decomposed)
    without_punctuation = _INSIGNIFICANT.sub(" ", without_marks)
    collapsed = _WHITESPACE.sub(" ", without_punctuation).strip()
    return collapsed.casefold()
