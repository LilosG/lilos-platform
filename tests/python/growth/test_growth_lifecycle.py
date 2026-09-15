from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from apps.api.app.growth.lifecycle import GrowthLifecycleService


def test_advance_batch_reconciles_and_dispatches_dependency_ready_work() -> None:
    organization_id = uuid4()
    initiative_id = uuid4()
    approving_user_id = uuid4()
    initiative = SimpleNamespace(
        organization_id=organization_id,
        id=initiative_id,
        status="executing",
        approved_by_user_id=approving_user_id,
    )
    session = MagicMock()
    session.scalars = AsyncMock(return_value=[initiative])
    growth = MagicMock()
    growth.reconcile = AsyncMock(return_value=initiative)
    growth.dispatch_ready = AsyncMock(return_value=[object(), object()])

    result = asyncio.run(
        GrowthLifecycleService(cast(Any, growth)).advance_batch(
            cast(Any, session),
            limit=100,
        )
    )

    assert result.scanned == 1
    assert result.reconciled == 1
    assert result.dispatched == 2
    growth.reconcile.assert_awaited_once_with(session, organization_id, initiative_id)
    growth.dispatch_ready.assert_awaited_once_with(
        session,
        organization_id,
        initiative_id,
        actor_id=approving_user_id,
        correlation_id=f"growth-lifecycle-{initiative_id}"[:64],
    )


def test_advance_batch_does_not_dispatch_without_durable_human_authority() -> None:
    initiative = SimpleNamespace(
        organization_id=uuid4(),
        id=uuid4(),
        status="approved",
        approved_by_user_id=None,
    )
    session = MagicMock()
    session.scalars = AsyncMock(return_value=[initiative])
    growth = MagicMock()
    growth.reconcile = AsyncMock(return_value=initiative)
    growth.dispatch_ready = AsyncMock()

    result = asyncio.run(
        GrowthLifecycleService(cast(Any, growth)).advance_batch(
            cast(Any, session),
        )
    )

    assert result.reconciled == 1
    assert result.dispatched == 0
    growth.dispatch_ready.assert_not_awaited()


def test_advance_batch_stops_after_reconciliation_reaches_terminal_state() -> None:
    candidate = SimpleNamespace(
        organization_id=uuid4(),
        id=uuid4(),
        status="executing",
        approved_by_user_id=uuid4(),
    )
    completed = SimpleNamespace(
        organization_id=candidate.organization_id,
        id=candidate.id,
        status="completed",
        approved_by_user_id=candidate.approved_by_user_id,
    )
    session = MagicMock()
    session.scalars = AsyncMock(return_value=[candidate])
    growth = MagicMock()
    growth.reconcile = AsyncMock(return_value=completed)
    growth.dispatch_ready = AsyncMock()

    result = asyncio.run(
        GrowthLifecycleService(cast(Any, growth)).advance_batch(
            cast(Any, session),
        )
    )

    assert result.reconciled == 1
    assert result.dispatched == 0
    growth.dispatch_ready.assert_not_awaited()
