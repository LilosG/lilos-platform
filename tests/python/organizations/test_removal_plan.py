"""The removal purge is derived from the metadata, and these tests keep it complete.

The workflow deletes whatever ``purge_plan`` returns. Nothing lists tables by hand, so the risk
is not a forgotten entry but a table the plan cannot see or one that is meant to survive without
saying so. These tests fail the build when a table gains an ``organization_id`` (or a reference
to one) and is neither purged nor explicitly retained.
"""

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import apps.worker.bootstrap  # noqa: F401 - register ORM models like the worker does
from apps.api.app.database.base import Base
from apps.api.app.organizations.removal import (
    PENDING_APPROVALS,
    RETAINED_TABLES,
    _scope,
    purge_plan,
)

ROOT = Path(__file__).resolve().parents[3]


def _scoped() -> set[str]:
    return {table.name for table in Base.metadata.tables.values() if "organization_id" in table.c}


def _referencing(scoped: set[str]) -> set[str]:
    return {
        table.name
        for table in Base.metadata.tables.values()
        if any(
            fk.referred_table.name in scoped and fk.referred_table is not table
            for fk in table.foreign_key_constraints
        )
    }


def test_every_organization_table_is_purged_or_explicitly_retained() -> None:
    plan = {table.name for table in purge_plan()}
    scoped = _scoped()
    needing_a_decision = (scoped | _referencing(scoped)) - plan - RETAINED_TABLES
    assert not needing_a_decision, (
        "These tables hold organization data but the removal workflow neither purges nor "
        f"retains them: {sorted(needing_a_decision)}"
    )


def test_only_the_audit_trail_and_the_tombstone_are_retained() -> None:
    assert {"audit_events", "organizations"} == RETAINED_TABLES
    assert not RETAINED_TABLES & {table.name for table in purge_plan()}


def test_the_plan_covers_tables_that_only_reference_an_organization_table() -> None:
    names = {table.name for table in purge_plan()}
    # No organization_id of its own: it reaches the organization through its delivery.
    assert "notification_delivery_attempts" in names
    assert {"workflow_runs", "jobs", "workflow_schedules", "locations"} <= names


def test_children_are_deleted_before_the_tables_they_reference() -> None:
    plan = purge_plan()
    position = {table: index for index, table in enumerate(plan)}
    for table in plan:
        for constraint in table.foreign_key_constraints:
            parent = constraint.referred_table
            if parent is table or parent not in position:
                continue
            assert position[table] < position[parent], (
                f"{table.name} references {parent.name} but would be deleted after it"
            )


def test_every_purged_table_has_a_primary_key_and_a_path_to_its_organization() -> None:
    plan = purge_plan()
    organization_id = uuid4()
    for table in plan:
        assert list(table.primary_key.columns), f"{table.name} has no primary key to batch on"
        # Raises when a table can neither filter on organization_id nor follow a foreign key.
        _scope(table, organization_id, set(plan))


def test_the_worker_registers_every_table_the_application_defines() -> None:
    """A table the worker never imported would silently survive a removal it runs."""
    program = (
        "import apps.worker.__main__  # the worker entrypoint, with everything it imports\n"
        "from apps.api.app.database.base import Base\n"
        "worker = {t.name for t in Base.metadata.tables.values()}\n"
        "import apps.api.app.main\n"
        "app = {t.name for t in Base.metadata.tables.values()}\n"
        "print(','.join(sorted(app - worker)))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    assert completed.stdout.strip() == "", (
        "apps/worker/bootstrap.py must import the models of: " + completed.stdout.strip()
    )


def test_pending_approval_retirements_name_real_tables_and_columns() -> None:
    for table_name, pending, retired in PENDING_APPROVALS:
        table = Base.metadata.tables[table_name]
        assert {"organization_id", "status"} <= set(table.c.keys()), table_name
        assert pending and retired not in pending
