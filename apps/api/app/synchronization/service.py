"""Pure normalization/diff helpers; dispatch remains a durable Phase 5 job."""

import hashlib
import json
from copy import deepcopy
from typing import Any


def normalize(document: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(document[key]) for key in sorted(document)}


def content_hash(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            normalize(document), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def deterministic_diff(desired: dict[str, Any], observed: dict[str, Any]) -> dict[str, object]:
    keys = sorted(set(desired) | set(observed))
    changes = {
        key: {"desired": deepcopy(desired.get(key)), "observed": deepcopy(observed.get(key))}
        for key in keys
        if desired.get(key) != observed.get(key)
    }
    return {"changed": bool(changes), "fields": changes}
