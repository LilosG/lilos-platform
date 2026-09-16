"""Regression coverage for the standalone publishing contract seed entrypoint."""

from __future__ import annotations

import subprocess
import sys


def test_publishing_contract_seed_registers_foreign_key_dependencies() -> None:
    """The Render pre-deploy seed must resolve PublishingTarget mapper dependencies."""
    code = """
from scripts.seed_publishing_target_contracts import PublishingTarget

sorted_tables = PublishingTarget.__mapper__._sorted_tables
assert any(table.name == "publishing_targets" for table in sorted_tables)
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
