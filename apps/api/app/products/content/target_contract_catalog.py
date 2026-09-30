"""Runtime lookup for verified repository publishing contracts.

The release reconciliation command owns the audited catalog. This boundary keeps
callers from mutating its shared documents when a publishing target is created.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.seed_publishing_target_contracts import CONTRACTS as CONTRACTS
from scripts.seed_publishing_target_contracts import SITE_CHANGE_PREFIXES, full_contract

__all__ = ["CONTRACTS", "contract_for_repository", "site_change_prefixes_for_repository"]


def contract_for_repository(repository_id: str) -> dict[str, Any]:
    """Return an isolated contract document (with its page map), or the safe default."""
    return deepcopy(full_contract(repository_id) or {})


def site_change_prefixes_for_repository(repository_id: str) -> list[str]:
    """Repository path prefixes a governed site change may edit; empty if none recorded."""
    return list(SITE_CHANGE_PREFIXES.get(repository_id, []))
