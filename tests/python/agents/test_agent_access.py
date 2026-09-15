import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.service import AdministrationService
from apps.api.app.agents.access import AgentAccessDecision, AgentAccessService
from apps.api.app.locations.enums import LocationStatus


def run_decision(
    service: AgentAccessService,
    session: object,
    organization_id: UUID,
    location_id: UUID,
    product_key: str,
) -> AgentAccessDecision:
    return asyncio.run(
        service.decision(
            cast(AsyncSession, session),
            organization_id=organization_id,
            location_id=location_id,
            product_key=product_key,
        )
    )


def service_with_entitlement_allowed() -> AgentAccessService:
    service = AgentAccessService(cast(AdministrationService, object()))
    service._entitlement_decision = AsyncMock(  # type: ignore[method-assign]
        return_value=AgentAccessDecision(True)
    )
    return service


def test_gbp_setup_required_location_is_operable_with_canonical_mapping() -> None:
    organization_id = uuid4()
    location_id = uuid4()
    location = SimpleNamespace(status=LocationStatus.SETUP_REQUIRED)
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[location, uuid4()]))
    service = service_with_entitlement_allowed()

    decision = run_decision(service, session, organization_id, location_id, "gbp")

    assert decision.eligible is True
    assert session.scalar.await_count == 2


def test_gbp_requires_canonical_provider_mapping() -> None:
    organization_id = uuid4()
    location_id = uuid4()
    location = SimpleNamespace(status=LocationStatus.ACTIVE)
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[location, None]))
    service = service_with_entitlement_allowed()

    decision = run_decision(service, session, organization_id, location_id, "gbp")

    assert decision.eligible is False
    assert decision.reason_code == "GBP_MAPPING_NOT_CONFIRMED"
    assert decision.status_code == 409


def test_gbp_rejects_paused_location_before_provider_lookup() -> None:
    organization_id = uuid4()
    location_id = uuid4()
    location = SimpleNamespace(status=LocationStatus.PAUSED)
    session = SimpleNamespace(scalar=AsyncMock(return_value=location))
    service = service_with_entitlement_allowed()

    decision = run_decision(service, session, organization_id, location_id, "gbp")

    assert decision.eligible is False
    assert decision.reason_code == "LOCATION_NOT_OPERABLE"
    assert session.scalar.await_count == 1


def test_non_gbp_agent_requires_active_location() -> None:
    organization_id = uuid4()
    location_id = uuid4()
    location = SimpleNamespace(status=LocationStatus.SETUP_REQUIRED)
    session = SimpleNamespace(scalar=AsyncMock(return_value=location))
    service = service_with_entitlement_allowed()

    decision = run_decision(service, session, organization_id, location_id, "seo")

    assert decision.eligible is False
    assert decision.reason_code == "LOCATION_NOT_ACTIVE"
