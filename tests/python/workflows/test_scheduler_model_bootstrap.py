"""The standalone scheduler must register foreign-key target models at startup."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_scheduler_entrypoint_registers_all_foreign_key_targets() -> None:
    probe = """
import apps.scheduler.__main__
from apps.api.app.database.base import Base
from apps.api.app.growth.models import GrowthInitiative
from apps.api.app.products.gbp.models import GBPPublication

assert "user_profiles" in Base.metadata.tables
assert "sync_change_intents" in Base.metadata.tables
growth_target = next(iter(GrowthInitiative.__table__.c.approved_by_user_id.foreign_keys))
sync_target = next(iter(GBPPublication.__table__.c.sync_change_intent_id.foreign_keys))
assert growth_target.column.table.name == "user_profiles"
assert sync_target.column.table.name == "sync_change_intents"
for table in Base.metadata.tables.values():
    for foreign_key in table.foreign_keys:
        foreign_key.column
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
