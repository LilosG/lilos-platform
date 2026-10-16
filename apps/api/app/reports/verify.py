"""Checks on text a model wrote: which numbers it states, who it credits, what it claims.

Used by the narrative and the result cards. A number is allowed only when it is one of the stored
figures the text is about, in a form a sentence may quote it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_DATE_MENTION = re.compile(
    rf"\b(?:{'|'.join(MONTHS)}|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{{1,2}}"
    r"(?:st|nd|rd|th)?\b(?:,?\s+\d{4})?",
    re.IGNORECASE,
)
_ORDINAL = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# "one" is left out on purpose: it is a pronoun far more often than a figure.
_WORD_NUMBERS: dict[str, int] = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
    "million": 1_000_000,
}
_WORD_NUMBER = re.compile(rf"\b(?:{'|'.join(_WORD_NUMBERS)})\b", re.IGNORECASE)
_AUTHORSHIP = re.compile(
    r"\bAI\b|\b(?:Claude|LILOs|Hermes|Anthropic|OpenAI|ChatGPT|GPT|artificial intelligence|"
    r"language model|machine[- ]generated|auto-?generated|assistant)\b",
    re.IGNORECASE,
)
_CAUSAL = re.compile(
    r"\b(?:because of|as a result of|resulted in|results? from|caused|causing|thanks to|"
    r"led to|driven by|owing to|attributable to|due to)\b",
    re.IGNORECASE,
)


def decimal_of(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def variants(value: Decimal) -> Iterator[Decimal]:
    """A stored figure, its magnitude and its roundings: how a sentence may quote it."""
    for candidate in (value, abs(value)):
        yield candidate
        yield candidate.quantize(Decimal("1"))
        yield candidate.quantize(Decimal("0.1"))
        yield candidate.quantize(Decimal("0.01"))


def leaves(document: object) -> Iterator[object]:
    if isinstance(document, dict):
        for value in document.values():
            yield from leaves(value)
    elif isinstance(document, list):
        for value in document:
            yield from leaves(value)
    else:
        yield document


def numbers_in(text: str) -> list[Decimal]:
    """Every number a text states: digits (with commas and decimals) and spelled-out numbers."""
    cleaned = _DATE_MENTION.sub(" ", text)
    cleaned = _ORDINAL.sub(" ", cleaned)
    cleaned = _LIST_MARKER.sub("", cleaned)
    found: list[Decimal] = []
    for whole, fraction in _NUMBER.findall(cleaned):
        number = decimal_of(whole.replace(",", "") + (f".{fraction}" if fraction else ""))
        if number is not None:
            found.append(number)
    found.extend(Decimal(_WORD_NUMBERS[word.lower()]) for word in _WORD_NUMBER.findall(cleaned))
    return found


def mentions_authorship(text: str) -> bool:
    return _AUTHORSHIP.search(text) is not None


def claims_cause(text: str) -> bool:
    return _CAUSAL.search(text) is not None
