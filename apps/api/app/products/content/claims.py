"""Claims a draft makes, and which of them are backed.

A draft may only assert what approved facts or the operator's own prompt back. Hermes
labels the claims it makes; this module normalises that labelling and adds a
deterministic backstop for invented specifics (years, prices, awards, addresses,
phone numbers) that appear in the body with no grounding. Anything unbacked becomes a
`needs_confirmation` claim, which blocks approval until the reviewer confirms or removes it.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import TypedDict, cast


class ClaimBasis(StrEnum):
    APPROVED_FACT = "approved_fact"
    OPERATOR_PROMPT = "operator_prompt"
    NEEDS_CONFIRMATION = "needs_confirmation"


class ClaimStatus(StrEnum):
    BACKED = "backed"
    NEEDS_CONFIRMATION = "needs_confirmation"
    CONFIRMED = "confirmed"


class ClaimRecord(TypedDict, total=False):
    claim_id: str
    text: str
    basis: str
    status: str
    detected: bool
    confirmed_by: str
    confirmed_at: str


_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_PRICE = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
_PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
_ADDRESS = re.compile(
    r"\b\d{2,5}\s+(?:[A-Z][\w.]*\s+){1,3}(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|"
    r"Way|Lane|Ln|Court|Ct)\b\.?"
)
_AWARD = re.compile(
    r"\b(?:award[- ]winning|voted\s+(?:best|#?1)|best of [A-Z][\w ]+|"
    r"won\s+(?:the\s+)?[A-Z][\w ]+ award|"
    r"family[- ]owned\s+since|established\s+in|founded\s+in|since\s+(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def claim_id(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).casefold().encode()).hexdigest()[:12]


def _norm(value: str) -> str:
    return " ".join(re.sub(r"[^\w$#]+", " ", value.casefold()).split())


def normalize_claims(raw: object, draft: str) -> list[ClaimRecord]:
    """Hermes's labelled claims, kept only when the quoted text really is in the draft."""
    if not isinstance(raw, list):
        return []
    draft_norm = _norm(draft)
    result: dict[str, ClaimRecord] = {}
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        text = " ".join(str(entry.get("text") or "").split())
        if not text or _norm(text) not in draft_norm:
            continue
        try:
            basis = ClaimBasis(str(entry.get("basis") or ""))
        except ValueError:
            # An unlabelled claim is an unbacked one, never a backed one.
            basis = ClaimBasis.NEEDS_CONFIRMATION
        status = (
            ClaimStatus.NEEDS_CONFIRMATION
            if basis is ClaimBasis.NEEDS_CONFIRMATION
            else ClaimStatus.BACKED
        )
        cid = claim_id(text)
        result[cid] = ClaimRecord(
            claim_id=cid, text=text[:500], basis=basis.value, status=status.value, detected=False
        )
    return list(result.values())


def detect_unbacked_specifics(
    draft: str,
    grounding_texts: Iterable[str],
    *,
    now: datetime | None = None,
) -> list[ClaimRecord]:
    """Sentences carrying a specific the grounding never states.

    Years, prices, phone numbers, street addresses and award/founding language are the
    specifics a model invents. Each is checked against the grounding text (approved facts,
    the prompt, the website knowledge the draft was given); a specific absent from all of
    it flags its sentence.
    """
    current_year = (now or datetime.now(UTC)).year
    grounding = _norm(" ".join(grounding_texts))
    flagged: dict[str, ClaimRecord] = {}
    for raw_sentence in _SENTENCE_SPLIT.split(draft):
        sentence = " ".join(raw_sentence.split())
        if len(sentence) < 8 or sentence.lstrip().startswith("#"):
            continue
        specifics: list[str] = []
        specifics += [
            m for m in _YEAR.findall(sentence) if int(m) not in {current_year, current_year + 1}
        ]
        specifics += _PRICE.findall(sentence)
        specifics += _PHONE.findall(sentence)
        specifics += [m.group(0) for m in _ADDRESS.finditer(sentence)]
        specifics += [m.group(0) for m in _AWARD.finditer(sentence)]
        if any(_norm(item) not in grounding for item in specifics):
            cid = claim_id(sentence)
            flagged[cid] = ClaimRecord(
                claim_id=cid,
                text=sentence[:500],
                basis=ClaimBasis.NEEDS_CONFIRMATION.value,
                status=ClaimStatus.NEEDS_CONFIRMATION.value,
                detected=True,
            )
    return list(flagged.values())


def merge_claims(*groups: Iterable[ClaimRecord]) -> list[ClaimRecord]:
    """Combine claim lists; a needs-confirmation label on either side wins."""
    merged: dict[str, ClaimRecord] = {}
    for group in groups:
        for claim in group:
            existing = merged.get(claim["claim_id"])
            if existing is None or claim["status"] == ClaimStatus.NEEDS_CONFIRMATION.value:
                merged[claim["claim_id"]] = claim
    return list(merged.values())


def unresolved_claims(validation_document: Mapping[str, object]) -> list[ClaimRecord]:
    claims = validation_document.get("claims")
    if not isinstance(claims, list):
        return []
    return [
        cast(ClaimRecord, claim)
        for claim in claims
        if isinstance(claim, dict) and claim.get("status") == ClaimStatus.NEEDS_CONFIRMATION.value
    ]
