import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.agents.hermes_client import (
    REQUIRED_FEATURES,
    REQUIRED_LILOS_TOOLS,
    HermesCapabilities,
    HermesRunsClient,
    HermesRuntimeError,
)
from apps.api.app.agents.models import AgentRun, AgentRunEvent, AgentSession
from apps.api.app.agents.service import AgentRuntimeService
from apps.api.app.agents.skills import skill_for_workflow
from apps.api.app.agents.tools import AgentToolDeniedError, AgentToolService
from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.service import ExecutionService
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


class AgentContext(TypedDict):
    organizations: list[UUID]
    locations: list[UUID]
    secondary_location_id: UUID
    workflow_run_id: UUID


def supported_capabilities() -> HermesCapabilities:
    return HermesCapabilities(
        runtime_version="0.20.5",
        model="hermes-agent",
        features={name: True for name in REQUIRED_FEATURES},
        endpoints={},
        runtime={"mode": "server_agent", "tool_execution": "server", "split_runtime": False},
        sanctioned_tools=tuple(sorted(REQUIRED_LILOS_TOOLS)),
        raw={},
    )


class RecordingHermesClient(HermesRunsClient):
    def __init__(self) -> None:
        super().__init__("http://hermes.invalid", "test-key", timeout_seconds=1)
        self.calls: list[tuple[str, str]] = []

    async def stop(self, hermes_run_id: str) -> dict[str, object]:
        self.calls.append(("stop", hermes_run_id))
        return {"status": "stopping"}

    async def steer(self, hermes_run_id: str, text: str) -> dict[str, object]:
        self.calls.append(("steer", f"{hermes_run_id}:{text}"))
        return {"accepted": True}

    async def approve(self, hermes_run_id: str, choice: str) -> dict[str, object]:
        self.calls.append(("approval", f"{hermes_run_id}:{choice}"))
        return {"resolved": 1}


class ReconnectingHermesClient(HermesRunsClient):
    def __init__(self) -> None:
        super().__init__("http://hermes.invalid", "test-key", timeout_seconds=1)
        self.create_calls = 0
        self.stream_calls = 0

    async def capabilities(self) -> HermesCapabilities:
        return supported_capabilities()

    async def create_run(self, **_kwargs: object) -> str:
        self.create_calls += 1
        return "run_native_reconnect"

    async def get_run(self, hermes_run_id: str) -> dict[str, object]:
        assert hermes_run_id == "run_native_reconnect"
        return {"run_id": hermes_run_id, "status": "running"}

    async def stream_events(self, hermes_run_id: str) -> AsyncIterator[dict[str, object]]:
        assert hermes_run_id == "run_native_reconnect"
        self.stream_calls += 1
        if self.stream_calls == 1:
            from apps.api.app.agents.hermes_client import HermesRuntimeError

            raise HermesRuntimeError("HERMES_EVENT_STREAM_FAILED", "transient disconnect")
        yield {
            "event": "run.completed",
            "output": "Completed after reconnect",
            "usage": {"input_tokens": 2, "output_tokens": 3},
        }


class AmbiguousCreateHermesClient(HermesRunsClient):
    def __init__(self) -> None:
        super().__init__("http://hermes.invalid", "test-key", timeout_seconds=1)

    async def capabilities(self) -> HermesCapabilities:
        return supported_capabilities()

    async def create_run(self, **_kwargs: object) -> str:
        raise HermesRuntimeError("HERMES_TIMEOUT", "ambiguous native create timeout")


@pytest.fixture
def agent_context(
    agent_session_factory: async_sessionmaker[AsyncSession],
) -> AgentContext:
    async def seed() -> AgentContext:
        async with agent_session_factory.begin() as session:
            organizations = [
                Organization(
                    name=f"Agent Org {index}",
                    slug=f"agent-org-{index}-{uuid4().hex[:6]}",
                    organization_type=OrganizationType.TEST,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                )
                for index in (1, 2)
            ]
            session.add_all(organizations)
            await session.flush()
            locations = [
                Location(
                    organization_id=organization.id,
                    name="Primary",
                    slug=f"primary-{uuid4().hex[:6]}",
                    location_type=LocationType.VIRTUAL,
                    status=LocationStatus.ACTIVE,
                    timezone="UTC",
                    country_code="US",
                    website_url="https://example.invalid",
                    is_primary=True,
                    version=1,
                )
                for organization in organizations
            ]
            session.add_all(locations)
            await session.flush()
            secondary_location = Location(
                organization_id=organizations[0].id,
                name="Secondary",
                slug=f"secondary-{uuid4().hex[:6]}",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://secondary.example.invalid",
                is_primary=False,
                version=1,
            )
            session.add(secondary_location)
            await session.flush()
            workflow = await ExecutionService().start_named(
                session,
                organizations[0].id,
                "agent.gbp",
                f"agent-binding-{uuid4().hex}",
                location_id=locations[0].id,
                input_document={},
                correlation_id="agent-binding-test",
                enqueue_job=False,
            )
            return {
                "organizations": [item.id for item in organizations],
                "locations": [item.id for item in locations],
                "secondary_location_id": secondary_location.id,
                "workflow_run_id": workflow.id,
            }

    return asyncio.run(seed())


@pytest.mark.integration
def test_agent_run_binds_workflow_ai_execution_and_opaque_session(
    agent_session_factory: async_sessionmaker[AsyncSession],
    agent_context: AgentContext,
) -> None:
    org_id = agent_context["organizations"][0]
    location_id = agent_context["locations"][0]
    workflow_run_id = agent_context["workflow_run_id"]
    capabilities = supported_capabilities()
    settings = Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "hermes_agent_session_retention_days": 30,
            "hermes_runtime_release": "v2026.8.19",
            "ai_hermes_model": "deepseek/deepseek-v4-flash-0731",
        }
    )

    async def scenario() -> None:
        async with agent_session_factory() as session:
            skill = skill_for_workflow("agent.gbp")
            run, scoped_session = await AgentRuntimeService()._prepare(
                session,
                settings,
                org_id,
                location_id,
                workflow_run_id,
                skill,
                capabilities,
                "agent-binding-test",
            )
            assert run.workflow_run_id == workflow_run_id
            assert run.ai_execution_id is not None
            assert scoped_session.hermes_session_key.startswith("lilos_mem_")
            assert run.hermes_session_id == scoped_session.hermes_session_key
            assert str(org_id) not in run.hermes_session_id
        assert run.capability_snapshot["runtime_version"] == "0.20.5"
        assert run.capability_snapshot["runtime_release"] == "v2026.8.19"
        assert run.capability_snapshot["api_model_alias"] == "hermes-agent"
        assert run.capability_snapshot["model"] == "deepseek/deepseek-v4-flash-0731"
        assert run.model_key == "deepseek/deepseek-v4-flash-0731"

    asyncio.run(scenario())


@pytest.mark.integration
def test_scoped_session_continuity_is_real_and_single_active_run_is_enforced(
    agent_session_factory: async_sessionmaker[AsyncSession],
    agent_context: AgentContext,
) -> None:
    async def scenario() -> None:
        org_id = agent_context["organizations"][0]
        location_id = agent_context["locations"][0]
        settings = Settings.model_validate({"environment": EnvironmentName.TEST})
        service = AgentRuntimeService()
        async with agent_session_factory() as session:
            first, first_session = await service._prepare(
                session,
                settings,
                org_id,
                location_id,
                agent_context["workflow_run_id"],
                skill_for_workflow("agent.gbp"),
                supported_capabilities(),
                "agent-continuity-one",
            )
            first.status = "completed"
            await session.commit()
            second_workflow = await ExecutionService().start_named(
                session,
                org_id,
                "agent.gbp",
                f"agent-continuity-two-{uuid4().hex}",
                location_id=location_id,
                input_document={},
                correlation_id="agent-continuity-two",
                enqueue_job=False,
            )
            second, second_session = await service._prepare(
                session,
                settings,
                org_id,
                location_id,
                second_workflow.id,
                skill_for_workflow("agent.gbp"),
                supported_capabilities(),
                "agent-continuity-two",
            )
            assert second_session.id == first_session.id
            assert second.hermes_session_id == first.hermes_session_id

            busy_workflow = await ExecutionService().start_named(
                session,
                org_id,
                "agent.gbp",
                f"agent-continuity-busy-{uuid4().hex}",
                location_id=location_id,
                input_document={},
                correlation_id="agent-continuity-busy",
                enqueue_job=False,
            )
            with pytest.raises(HermesRuntimeError) as exc:
                await service._prepare(
                    session,
                    settings,
                    org_id,
                    location_id,
                    busy_workflow.id,
                    skill_for_workflow("agent.gbp"),
                    supported_capabilities(),
                    "agent-continuity-busy",
                )
            assert getattr(exc.value, "safe_code", None) == "HERMES_SCOPED_SESSION_BUSY"

    asyncio.run(scenario())


@pytest.mark.integration
def test_structured_events_are_bounded_and_private_reasoning_is_not_persisted(
    agent_session_factory: async_sessionmaker[AsyncSession],
    agent_context: AgentContext,
) -> None:
    async def scenario() -> None:
        settings = Settings.model_validate(
            {"environment": EnvironmentName.TEST, "hermes_agent_event_limit": 25}
        )
        async with agent_session_factory() as session:
            run, _ = await AgentRuntimeService()._prepare(
                session,
                settings,
                agent_context["organizations"][0],
                agent_context["locations"][0],
                agent_context["workflow_run_id"],
                skill_for_workflow("agent.gbp"),
                supported_capabilities(),
                "agent-event-test",
            )
            await AgentRuntimeService()._persist_event(
                session,
                settings,
                run,
                {"event": "reasoning.available", "text": "private chain of thought"},
            )
            await AgentRuntimeService()._persist_event(
                session,
                settings,
                run,
                {
                    "event": "run.completed",
                    "output": {"api_key": "must-not-persist"},
                    "usage": {"input_tokens": 4, "output_tokens": 7},
                },
            )
            events = list(
                await session.scalars(
                    select(AgentRunEvent).where(AgentRunEvent.agent_run_id == run.id)
                )
            )
            assert len(events) == 1
            assert events[0].event_type == "run.completed"
            assert "must-not-persist" not in str(events[0].event_document)
            assert events[0].event_document["output"] == "[REDACTED_SECRET_BEARING_OUTPUT]"
            assert run.event_count == 1
            assert run.input_tokens == 4
            assert run.output_tokens == 7

    asyncio.run(scenario())


@pytest.mark.integration
def test_tool_audit_records_safe_source_metadata_and_location_scoped_insights(
    agent_session_factory: async_sessionmaker[AsyncSession],
    agent_context: AgentContext,
) -> None:
    async def scenario() -> None:
        org_id = agent_context["organizations"][0]
        location_id = agent_context["locations"][0]
        settings = Settings.model_validate({"environment": EnvironmentName.TEST})
        async with agent_session_factory() as session:
            workflow = await ExecutionService().start_named(
                session,
                org_id,
                "agent.insights",
                f"agent-insights-{uuid4().hex}",
                location_id=location_id,
                input_document={},
                correlation_id="agent-insights-test",
                enqueue_job=False,
            )
            await ExecutionService().start_named(
                session,
                org_id,
                "agent.insights",
                f"agent-insights-secondary-{uuid4().hex}",
                location_id=agent_context["secondary_location_id"],
                input_document={},
                correlation_id="agent-insights-secondary-test",
                enqueue_job=False,
            )
            run, _ = await AgentRuntimeService()._prepare(
                session,
                settings,
                org_id,
                location_id,
                workflow.id,
                skill_for_workflow("agent.insights"),
                supported_capabilities(),
                "agent-insights-test",
            )
            run.status = "running"
            result = await AgentToolService().invoke(session, run, "read_cross_product_summary", {})
            assert result["source_references"] == [f"insights-summary:{run.id}"]
            assert run.source_references == [f"insights-summary:{run.id}"]
            data = result["data"]
            assert isinstance(data, dict)
            assert data["workflow_runs"] == {"queued": 2}
            audit = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.resource_id == run.id,
                    AuditEvent.event_type == "agent.tool.invoked",
                )
            )
            assert audit is not None
            assert audit.result == "succeeded"
            assert audit.event_metadata["argument_names"] == []
            assert isinstance(audit.event_metadata["result_hash"], str)
            assert int(audit.event_metadata["result_bytes"]) > 0
            assert audit.event_metadata["source_references"] == [f"insights-summary:{run.id}"]
            assert audit.correlation_id == "agent-insights-test"
            assert str(agent_context["organizations"][1]) not in str(result)

    asyncio.run(scenario())


@pytest.mark.integration
def test_native_stop_steer_and_approval_controls_update_bound_run(
    agent_session_factory: async_sessionmaker[AsyncSession],
    agent_context: AgentContext,
) -> None:
    async def scenario() -> None:
        org_id = agent_context["organizations"][0]
        settings = Settings.model_validate({"environment": EnvironmentName.TEST})
        client = RecordingHermesClient()
        service = AgentRuntimeService(client_factory=lambda _settings: client)
        async with agent_session_factory() as session:
            run, _ = await service._prepare(
                session,
                settings,
                org_id,
                agent_context["locations"][0],
                agent_context["workflow_run_id"],
                skill_for_workflow("agent.gbp"),
                supported_capabilities(),
                "agent-control-test",
            )
            run.hermes_run_id = "run_native_control"
            run.status = "running"
            await service.control(
                session,
                settings,
                org_id,
                run.id,
                "steer",
                text="Use the newest crawl evidence",
                choice=None,
                actor_id=uuid4(),
                correlation_id="agent-steer-test",
            )
            run.status = "waiting_approval"
            run.current_approval = {"approval_id": "approval-1"}
            await service.control(
                session,
                settings,
                org_id,
                run.id,
                "approval",
                text=None,
                choice="once",
                actor_id=uuid4(),
                correlation_id="agent-approval-test",
            )
            assert run.status == "running"
            assert run.current_approval is None
            await service.control(
                session,
                settings,
                org_id,
                run.id,
                "stop",
                text=None,
                choice=None,
                actor_id=uuid4(),
                correlation_id="agent-stop-test",
            )
            assert run.status == "stopping"
            assert client.calls == [
                ("steer", "run_native_control:Use the newest crawl evidence"),
                ("approval", "run_native_control:once"),
                ("stop", "run_native_control"),
            ]

    asyncio.run(scenario())


@pytest.mark.integration
def test_retry_reconnects_existing_hermes_run_without_duplicate_creation(
    agent_session_factory: async_sessionmaker[AsyncSession],
    agent_context: AgentContext,
) -> None:
    async def scenario() -> None:
        client = ReconnectingHermesClient()
        service = AgentRuntimeService(client_factory=lambda _settings: client)
        settings = Settings.model_validate(
            {"environment": EnvironmentName.TEST, "ai_provider": "hermes"}
        )
        async with agent_session_factory() as session:

            async def execute() -> JobOutcome:
                return await service.execute_workflow(
                    session,
                    settings,
                    organization_id=agent_context["organizations"][0],
                    location_id=agent_context["locations"][0],
                    workflow_run_id=agent_context["workflow_run_id"],
                    workflow_key="agent.gbp",
                    input_document={},
                    correlation_id="agent-reconnect-test",
                )

            first = await execute()
            second = await execute()
            assert first.result == "retryable_failure"
            assert first.safe_error == "HERMES_EVENT_STREAM_FAILED"
            assert second.result == "succeeded"
            assert client.create_calls == 1
            assert client.stream_calls == 2
            run = await session.scalar(
                select(AgentRun).where(AgentRun.workflow_run_id == agent_context["workflow_run_id"])
            )
            assert run is not None
            assert run.status == "completed"
            assert run.hermes_run_id == "run_native_reconnect"

    asyncio.run(scenario())


@pytest.mark.integration
def test_ambiguous_native_create_fails_closed_and_rotates_tool_binding(
    agent_session_factory: async_sessionmaker[AsyncSession],
    agent_context: AgentContext,
) -> None:
    async def scenario() -> None:
        client = AmbiguousCreateHermesClient()
        service = AgentRuntimeService(client_factory=lambda _settings: client)
        settings = Settings.model_validate(
            {"environment": EnvironmentName.TEST, "ai_provider": "hermes"}
        )
        org_id = agent_context["organizations"][0]
        location_id = agent_context["locations"][0]
        async with agent_session_factory() as session:
            outcome = await service.execute_workflow(
                session,
                settings,
                organization_id=org_id,
                location_id=location_id,
                workflow_run_id=agent_context["workflow_run_id"],
                workflow_key="agent.gbp",
                input_document={},
                correlation_id="agent-ambiguous-create",
            )
            assert outcome.result == "permanent_failure"
            assert outcome.safe_error == "HERMES_TIMEOUT"
            failed_run = await session.scalar(
                select(AgentRun).where(AgentRun.workflow_run_id == agent_context["workflow_run_id"])
            )
            assert failed_run is not None
            old_session_id = failed_run.hermes_session_id
            assert failed_run.status == "failed"
            with pytest.raises(AgentToolDeniedError, match="not bound"):
                await AgentToolService().bound_run(session, old_session_id)

            next_workflow = await ExecutionService().start_named(
                session,
                org_id,
                "agent.gbp",
                f"agent-after-ambiguous-{uuid4().hex}",
                location_id=location_id,
                input_document={},
                correlation_id="agent-after-ambiguous",
                enqueue_job=False,
            )
            next_run, _ = await service._prepare(
                session,
                settings,
                org_id,
                location_id,
                next_workflow.id,
                skill_for_workflow("agent.gbp"),
                supported_capabilities(),
                "agent-after-ambiguous",
            )
            assert next_run.hermes_session_id != old_session_id

    asyncio.run(scenario())


@pytest.mark.integration
def test_cross_tenant_model_scope_is_denied_and_audited(
    agent_session_factory: async_sessionmaker[AsyncSession],
    agent_context: AgentContext,
) -> None:
    org_id = agent_context["organizations"][0]
    other_org_id = agent_context["organizations"][1]
    location_id = agent_context["locations"][0]
    workflow_run_id = agent_context["workflow_run_id"]

    async def scenario() -> None:
        async with agent_session_factory.begin() as session:
            scoped_session = AgentSession(
                organization_id=org_id,
                location_id=location_id,
                skill_key="gbp.operator",
                namespace_hash=uuid4().hex + uuid4().hex,
                hermes_session_key=f"lilos_mem_{uuid4().hex}",
                status="active",
                expires_at=datetime.now(UTC) + timedelta(days=30),
                version=1,
            )
            session.add(scoped_session)
            await session.flush()
            run = AgentRun(
                organization_id=org_id,
                location_id=location_id,
                workflow_run_id=workflow_run_id,
                agent_session_id=scoped_session.id,
                skill_key="gbp.operator",
                skill_version=1,
                hermes_session_id=f"lilos_run_{uuid4().hex}",
                correlation_id="agent-cross-tenant-test",
                status="running",
                provider_key="hermes",
                capability_snapshot={"features": {}},
                output_references=[],
                event_count=0,
            )
            session.add(run)
            await session.flush()
            with pytest.raises(AgentToolDeniedError):
                await AgentToolService().invoke(
                    session,
                    run,
                    "read_gbp_state",
                    {"organization_id": str(other_org_id), "location_id": str(uuid4())},
                )
            audit = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.resource_id == run.id,
                    AuditEvent.event_type == "agent.tool.invoked",
                )
            )
            assert audit is not None
            assert audit.result == "denied"
            assert audit.event_metadata["argument_names"] == ["location_id", "organization_id"]
            assert str(other_org_id) not in str(audit.event_metadata)

    asyncio.run(scenario())


@pytest.mark.integration
def test_database_rejects_cross_tenant_agent_session_binding(
    agent_session_factory: async_sessionmaker[AsyncSession],
    agent_context: AgentContext,
) -> None:
    async def scenario() -> None:
        first_org = agent_context["organizations"][0]
        second_org = agent_context["organizations"][1]
        async with agent_session_factory() as session:
            first_session = AgentSession(
                organization_id=first_org,
                location_id=agent_context["locations"][0],
                skill_key="gbp.operator",
                namespace_hash=uuid4().hex + uuid4().hex,
                hermes_session_key=f"lilos_mem_{uuid4().hex}",
                status="active",
                expires_at=datetime.now(UTC) + timedelta(days=30),
                version=1,
            )
            session.add(first_session)
            await session.flush()
            second_workflow = await ExecutionService().start_named(
                session,
                second_org,
                "agent.gbp",
                f"agent-cross-binding-{uuid4().hex}",
                location_id=agent_context["locations"][1],
                input_document={},
                correlation_id="agent-cross-binding-test",
                enqueue_job=False,
            )
            session.add(
                AgentRun(
                    organization_id=second_org,
                    location_id=agent_context["locations"][1],
                    workflow_run_id=second_workflow.id,
                    agent_session_id=first_session.id,
                    skill_key="gbp.operator",
                    skill_version=1,
                    hermes_session_id=f"lilos_run_{uuid4().hex}",
                    correlation_id="agent-cross-binding-test",
                    status="queued",
                    provider_key="hermes",
                    capability_snapshot={"features": {}},
                    output_references=[],
                    event_count=0,
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()

    asyncio.run(scenario())


@pytest.mark.integration
def test_scoped_session_reset_does_not_affect_other_tenant(
    agent_session_factory: async_sessionmaker[AsyncSession],
    agent_context: AgentContext,
) -> None:
    settings = Settings.model_validate({"environment": EnvironmentName.TEST})
    organizations = agent_context["organizations"]
    locations = agent_context["locations"]
    service = AgentRuntimeService()

    async def scenario() -> None:
        async with agent_session_factory.begin() as session:
            first = await service._session(
                session,
                settings,
                organizations[0],
                locations[0],
                "seo.operator",
            )
            second = await service._session(
                session,
                settings,
                organizations[1],
                locations[1],
                "seo.operator",
            )
            first_key = first.hermes_session_key
            second_key = second.hermes_session_key
            reset = await service.reset_session(
                session,
                settings,
                organizations[0],
                locations[0],
                "seo.operator",
                actor_id=uuid4(),
                correlation_id="agent-session-reset",
            )
            assert reset.hermes_session_key != first_key
            await session.refresh(second)
            assert second.hermes_session_key == second_key

    asyncio.run(scenario())
