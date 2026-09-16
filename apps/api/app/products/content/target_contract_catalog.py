"""Runtime lookup for verified repository publishing contracts.

The release reconciliation command owns the audited catalog. This boundary keeps
callers from mutating its shared documents when a publishing target is created.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.seed_publishing_target_contracts import CONTRACTS


def contract_for_repository(repository_id: str) -> dict[str, Any]:
    """Return an isolated contract document, or the safe universal default."""
    return deepcopy(CONTRACTS.get(repository_id, {}))
