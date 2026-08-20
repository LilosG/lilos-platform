"""Authenticated and authorized Phase 4 shared-administration routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.administration.contracts import (
    BusinessFactDecision,
    BusinessFactPropose,
    ChecklistComplete,
    ChecklistItemCreate,
    ConfigurationCreate,
    DataResponse,
    EntitlementCreate,
    EntitlementTransition,
    ExpectedVersion,
    FeatureFlagCreate,
    OffboardingCreate,
    OffboardingStepComplete,
    OffboardingTransition,
    PolicyCreate,
    RuntimeControlCreate,
    ServiceAssignmentCreate,
    ServiceCreate,
    ServiceUpdate,
)
from apps.api.app.administration.service import AdministrationService
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.schemas import ResponseMeta


async def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}",
    tags=["shared-administration"],
    dependencies=[Depends(get_authenticated_principal), Depends(no_store)],
)
service = AdministrationService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def policy(permission: str, *, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            permission, ScopeType.ORGANIZATION, AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1
        )
    )


def response(request: Request, data: Any) -> DataResponse:
    return DataResponse(
        data=data, meta=ResponseMeta(correlation_id=request_correlation_id(request))
    )


def row(item: Any) -> dict[str, Any]:
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


@router.get("/services", response_model=DataResponse)
async def list_services(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _: Annotated[AuthorizationDecision | None, policy("services.read")],
) -> DataResponse:
    return response(
        request,
        [row(item) for item in await service.services.list_services(session, organization_id)],
    )


@router.post("/services", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    request: Request,
    organization_id: UUID,
    command: ServiceCreate,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("services.manage")] = None,
) -> DataResponse:
    item = await service.create_service(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.put("/services/{service_id}", response_model=DataResponse)
async def update_service(
    request: Request,
    organization_id: UUID,
    service_id: UUID,
    command: ServiceUpdate,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("services.manage")] = None,
) -> DataResponse:
    item = await service.update_service(
        session,
        organization_id,
        service_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.post("/services/{service_id}/archive", response_model=DataResponse)
async def archive_service(
    request: Request,
    organization_id: UUID,
    service_id: UUID,
    command: ExpectedVersion,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("services.manage", aal2=True)] = None,
) -> DataResponse:
    item = await service.archive_service(
        session,
        organization_id,
        service_id,
        command.expected_version,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.post(
    "/service-assignments", response_model=DataResponse, status_code=status.HTTP_201_CREATED
)
async def assign_service(
    request: Request,
    organization_id: UUID,
    command: ServiceAssignmentCreate,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("services.manage")] = None,
) -> DataResponse:
    item = await service.assign_service(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.get("/services/effective", response_model=DataResponse)
async def effective_services(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    location_id: UUID | None = None,
    _: Annotated[AuthorizationDecision | None, policy("services.read")] = None,
) -> DataResponse:
    return response(
        request,
        [
            row(item)
            for item in await service.effective_services(session, organization_id, location_id)
        ],
    )


@router.post("/service-assignments/{assignment_id}/remove", response_model=DataResponse)
async def remove_service_assignment(
    request: Request,
    organization_id: UUID,
    assignment_id: UUID,
    command: ExpectedVersion,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("services.manage")] = None,
) -> DataResponse:
    item = await service.remove_service_assignment(
        session,
        organization_id,
        assignment_id,
        command.expected_version,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.post("/business-facts", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
async def propose_fact(
    request: Request,
    organization_id: UUID,
    command: BusinessFactPropose,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("business_facts.propose")] = None,
) -> DataResponse:
    item = await service.propose_fact(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.post("/business-facts/{revision_id}/decision", response_model=DataResponse)
async def decide_fact(
    request: Request,
    organization_id: UUID,
    revision_id: UUID,
    command: BusinessFactDecision,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("business_facts.approve", aal2=True)] = None,
) -> DataResponse:
    item = await service.decide_fact(
        session,
        organization_id,
        revision_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.get("/business-facts/resolve/{fact_key:path}", response_model=DataResponse)
async def resolve_fact(
    request: Request,
    organization_id: UUID,
    fact_key: str,
    session: DatabaseSession,
    location_id: UUID | None = None,
    _: Annotated[AuthorizationDecision | None, policy("business_facts.read")] = None,
) -> DataResponse:
    return response(
        request,
        await service.resolve_fact(session, organization_id, fact_key, location_id=location_id),
    )


@router.post("/business-facts/reconcile", response_model=DataResponse)
async def reconcile_business_facts(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("business_facts.propose")] = None,
) -> DataResponse:
    """Derive business-fact candidates from the client's authoritative data.

    Proposes ``system_derived`` candidates for the keys products require so an
    operator can confirm them in one place rather than typing internal fact
    keys by hand. Never auto-approves; preserves the human-confirmation gate.
    """
    return response(
        request,
        await service.reconcile_business_facts(
            session,
            organization_id,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        ),
    )


@router.get("/business-knowledge/coverage", response_model=DataResponse)
async def business_knowledge_coverage(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _: Annotated[AuthorizationDecision | None, policy("business_facts.read")] = None,
) -> DataResponse:
    """Return knowledge coverage summary for Business Information display."""
    from apps.api.app.administration.knowledge_service import BusinessKnowledgeService

    svc = BusinessKnowledgeService()
    return response(request, await svc.get_coverage(session, organization_id=organization_id))


@router.get("/business-facts/candidates", response_model=DataResponse)
async def list_business_fact_candidates(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _: Annotated[AuthorizationDecision | None, policy("business_facts.read")] = None,
) -> DataResponse:
    """List proposed business facts awaiting operator confirmation."""
    items = await service.facts.list_pending(session, organization_id)
    return response(request, [row(item) for item in items])


@router.get("/business-facts/effective", response_model=DataResponse)
async def list_effective_business_facts(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _: Annotated[AuthorizationDecision | None, policy("business_facts.read")] = None,
) -> DataResponse:
    """List every active governed business fact currently in effect."""
    items = await service.effective_facts(session, organization_id)
    return response(request, items)


@router.get("/products", response_model=DataResponse)
async def list_products(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _: Annotated[AuthorizationDecision | None, policy("products.read")],
) -> DataResponse:
    return response(request, [row(item) for item in await service.catalog.list_products(session)])


@router.post(
    "/product-entitlements", response_model=DataResponse, status_code=status.HTTP_201_CREATED
)
async def create_entitlement(
    request: Request,
    organization_id: UUID,
    command: EntitlementCreate,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[
        AuthorizationDecision | None, policy("products.entitlements.manage", aal2=True)
    ] = None,
) -> DataResponse:
    item = await service.create_entitlement(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.post("/product-entitlements/{entitlement_id}/transition", response_model=DataResponse)
async def transition_entitlement(
    request: Request,
    organization_id: UUID,
    entitlement_id: UUID,
    command: EntitlementTransition,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[
        AuthorizationDecision | None, policy("products.entitlements.manage", aal2=True)
    ] = None,
) -> DataResponse:
    item = await service.transition_entitlement(
        session,
        organization_id,
        entitlement_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.get("/products/{product_key}/readiness", response_model=DataResponse)
async def readiness(
    request: Request,
    organization_id: UUID,
    product_key: str,
    session: DatabaseSession,
    _: Annotated[AuthorizationDecision | None, policy("products.read")],
) -> DataResponse:
    return response(request, await service.readiness(session, organization_id, product_key))


@router.post("/configuration", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
async def create_configuration(
    request: Request,
    organization_id: UUID,
    command: ConfigurationCreate,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("configuration.manage")] = None,
) -> DataResponse:
    item = await service.create_configuration(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.post("/configuration/{revision_id}/approve", response_model=DataResponse)
async def approve_configuration(
    request: Request,
    organization_id: UUID,
    revision_id: UUID,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("configuration.manage", aal2=True)] = None,
) -> DataResponse:
    item = await service.approve_configuration(
        session,
        organization_id,
        revision_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.get("/configuration/resolve/{definition_key:path}", response_model=DataResponse)
async def resolve_configuration(
    request: Request,
    organization_id: UUID,
    definition_key: str,
    session: DatabaseSession,
    location_id: UUID | None = None,
    product_key: str | None = None,
    _: Annotated[AuthorizationDecision | None, policy("configuration.read")] = None,
) -> DataResponse:
    return response(
        request,
        await service.resolve_configuration(
            session,
            organization_id,
            definition_key,
            location_id=location_id,
            product_key=product_key,
        ),
    )


@router.post("/policies", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    request: Request,
    organization_id: UUID,
    command: PolicyCreate,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("policies.manage")] = None,
) -> DataResponse:
    item = await service.create_policy(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.post("/policies/{revision_id}/approve", response_model=DataResponse)
async def approve_policy(
    request: Request,
    organization_id: UUID,
    revision_id: UUID,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("policies.manage", aal2=True)] = None,
) -> DataResponse:
    item = await service.approve_policy(
        session,
        organization_id,
        revision_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.get("/policies/effective/{category}", response_model=DataResponse)
async def effective_policies(
    request: Request,
    organization_id: UUID,
    category: str,
    session: DatabaseSession,
    product_key: str | None = None,
    _: Annotated[AuthorizationDecision | None, policy("policies.read")] = None,
) -> DataResponse:
    items = await service.effective_policies(
        session, organization_id, category, product_key=product_key
    )
    return response(request, [row(item) for item in items])


@router.post("/feature-flags", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
async def create_flag(
    request: Request,
    organization_id: UUID,
    command: FeatureFlagCreate,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("feature_flags.manage")] = None,
) -> DataResponse:
    item = await service.create_flag(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.get("/feature-flags/{flag_key:path}", response_model=DataResponse)
async def resolve_flag(
    request: Request,
    organization_id: UUID,
    flag_key: str,
    session: DatabaseSession,
    location_id: UUID | None = None,
    _: Annotated[AuthorizationDecision | None, policy("feature_flags.read")] = None,
) -> DataResponse:
    item = await service.resolve_flag(session, organization_id, flag_key, location_id=location_id)
    return response(request, row(item) if item else None)


@router.post("/runtime-controls", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
async def create_control(
    request: Request,
    organization_id: UUID,
    command: RuntimeControlCreate,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("runtime_controls.manage", aal2=True)] = None,
) -> DataResponse:
    item = await service.create_control(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.get("/runtime-controls/{capability:path}", response_model=DataResponse)
async def resolve_control(
    request: Request,
    organization_id: UUID,
    capability: str,
    session: DatabaseSession,
    location_id: UUID | None = None,
    product_key: str | None = None,
    _: Annotated[AuthorizationDecision | None, policy("runtime_controls.read")] = None,
) -> DataResponse:
    return response(
        request,
        await service.resolve_control(
            session, organization_id, capability, location_id=location_id, product_key=product_key
        ),
    )


@router.post("/onboarding/items", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
async def create_checklist_item(
    request: Request,
    organization_id: UUID,
    command: ChecklistItemCreate,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("onboarding.manage")] = None,
) -> DataResponse:
    item = await service.create_checklist_item(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.post("/onboarding/items/{item_id}/complete", response_model=DataResponse)
async def complete_checklist_item(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    command: ChecklistComplete,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("onboarding.manage")] = None,
) -> DataResponse:
    item = await service.complete_checklist_item(
        session,
        organization_id,
        item_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.get("/onboarding", response_model=DataResponse)
async def onboarding(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _: Annotated[AuthorizationDecision | None, policy("onboarding.read")],
) -> DataResponse:
    return response(request, await service.onboarding(session, organization_id))


@router.post("/offboarding", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
async def create_offboarding(
    request: Request,
    organization_id: UUID,
    command: OffboardingCreate,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("offboarding.manage", aal2=True)] = None,
) -> DataResponse:
    item = await service.create_offboarding(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.post("/offboarding/{plan_id}/transition", response_model=DataResponse)
async def transition_offboarding(
    request: Request,
    organization_id: UUID,
    plan_id: UUID,
    command: OffboardingTransition,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("offboarding.manage", aal2=True)] = None,
) -> DataResponse:
    item = await service.transition_offboarding(
        session,
        organization_id,
        plan_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))


@router.post("/offboarding/{plan_id}/steps/{step_id}/complete", response_model=DataResponse)
async def complete_offboarding_step(
    request: Request,
    organization_id: UUID,
    plan_id: UUID,
    step_id: UUID,
    command: OffboardingStepComplete,
    session: DatabaseSession,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision | None, policy("offboarding.manage", aal2=True)] = None,
) -> DataResponse:
    item = await service.complete_offboarding_step(
        session,
        organization_id,
        plan_id,
        step_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, row(item))
