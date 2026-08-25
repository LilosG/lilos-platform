"""LILOs control-plane service for native Hermes runs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.service import AdministrationService
from apps.api.app.agents.hermes_client import (
    REQUIRED_FEATURES,
    HermesCapabilities,
    HermesRunsClient,
    HermesRuntimeError,
)
from apps.api.app.agents.models import AgentRun, AgentRunEvent, AgentSession
from apps.api.app.agents.safety import has_secret_key, redact_text, safe_event_document
from apps.api.app.agents.skills import AgentSkill, skill_for_workflow
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.execution.contracts import JobOutcome

TERMINAL_HERMES_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_AGENT_STATUSES = {"queued", "running", "waiting_approval", "stopping"}


def build_hermes_runs_client(settings: Settings) -> HermesRunsClient:
    if not settings.ai_hermes_base_url or not settings.ai_hermes_api_key:
        raise HermesRuntimeError("HERMES_NOT_CONFIGURED", "Hermes runtime is not configured")
    return HermesRunsClient(
        settings.ai_hermes_base_url,
        settings.ai_hermes_api_key,
        timeout_seconds=settings.ai_hermes_timeout_seconds,
    )


class AgentRuntimeService:
    def __init__(
        self,
        *,
        client_factory: Callable[[Settings], HermesRunsClient] = build_hermes_runs_client,
    ) -> None:
        self._client_factory = client_factory
        self.audit = AuditEventService()
        self.administration = AdministrationService()

    async def _delete_scoped_hermes_session(
        self, settings: Settings, hermes_session_id: str
    ) -> None:
        if settings.ai_provider != "hermes":
            return
        if not settings.ai_hermes_base_url or not settings.ai_hermes_api_key:
            if settings.environment.value == "production":
                raise HermesRuntimeError(
                    "HERMES_NOT_CONFIGURED", "Hermes session reset is not configured"
                )
            return
        await self._client_factory(settings).delete_session(hermes_session_id)

    @staticmethod
    def _namespace_hash(organization_id: UUID, location_id: UUID | None, skill_key: str) -> str:
        raw = f"{organization_id}:{location_id or 'organization'}:{skill_key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _session(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        location_id: UUID | None,
        skill_key: str,
    ) -> AgentSession:
        now = datetime.now(UTC)
        namespace = self._namespace_hash(organization_id, location_id, skill_key)
        row = await session.scalar(
            select(AgentSession)
            .where(
                AgentSession.organization_id == organization_id,
                AgentSession.location_id == location_id,
                AgentSession.skill_key == skill_key,
                AgentSession.namespace_hash == namespace,
            )
            .with_for_update()
        )
        if row is None:
            row = AgentSession(
                organization_id=organization_id,
                location_id=location_id,
                skill_key=skill_key,
                namespace_hash=namespace,
                hermes_session_key=f"lilos_mem_{uuid4().hex}",
                status="active",
                expires_at=now + timedelta(days=settings.hermes_agent_session_retention_days),
                version=1,
            )
            session.add(row)
            await session.flush()
        elif row.status != "active" or row.expires_at <= now:
            if await session.scalar(
                select(func.count())
                .select_from(AgentRun)
                .where(
                    AgentRun.organization_id == organization_id,
                    AgentRun.agent_session_id == row.id,
                    AgentRun.status.in_(ACTIVE_AGENT_STATUSES),
                )
            ):
                raise HermesRuntimeError(
                    "HERMES_SCOPED_SESSION_BUSY",
                    "An active Hermes run prevents scoped session expiry",
                )
            await self._delete_scoped_hermes_session(settings, row.hermes_session_key)
            row.hermes_session_key = f"lilos_mem_{uuid4().hex}"
            row.status = "active"
            row.reset_at = now
            row.expires_at = now + timedelta(days=settings.hermes_agent_session_retention_days)
            row.version += 1
            await session.flush()
        return row

    async def reset_session(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        location_id: UUID | None,
        skill_key: str,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> AgentSession:
        row = await self._session(session, settings, organization_id, location_id, skill_key)
        if await session.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(
                AgentRun.organization_id == organization_id,
                AgentRun.agent_session_id == row.id,
                AgentRun.status.in_(ACTIVE_AGENT_STATUSES),
            )
        ):
            raise ValueError("active agent run prevents session reset")
        now = datetime.now(UTC)
        await self._delete_scoped_hermes_session(settings, row.hermes_session_key)
        row.hermes_session_key = f"lilos_mem_{uuid4().hex}"
        row.reset_at = now
        row.expires_at = now + timedelta(days=settings.hermes_agent_session_retention_days)
        row.version += 1
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type="agent.session.reset",
                action="agent.session.reset",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER,
                actor_id=actor_id,
                organization_id=organization_id,
                location_id=location_id,
                product_key="insights"
                if skill_key.startswith("insights.")
                else skill_key.split(".")[0],
                resource_type="agent_session",
                resource_id=row.id,
                correlation_id=correlation_id,
                summary="Scoped Hermes agent session reset.",
                metadata={"skill_key": skill_key, "session_version": row.version},
            ),
        )
        return row

    async def _task_and_execution(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID | None,
        workflow_run_id: UUID,
        skill: AgentSkill,
    ) -> AIExecution:
        task_key = f"agent.{skill.key}"
        task = await session.scalar(
            select(AITaskDefinition).where(
                AITaskDefinition.key == task_key,
                AITaskDefinition.version == skill.version,
            )
        )
        if task is None:
            task = AITaskDefinition(
                key=task_key,
                version=skill.version,
                owning_product=skill.product_key,
                purpose=skill.title,
                input_schema={"objective": "string", "context_reference": "string|null"},
                output_schema={
                    "what_changed": "array",
                    "evidence": "array",
                    "requires_attention": "array",
                    "recommended_actions": "array",
                    "proposal_references": "array",
                },
                risk_level="medium",
                maximum_cost_microunits=0,
                maximum_latency_ms=300_000,
                requires_human_review=True,
                retention_policy_key="agents.events.bounded_v1",
                status="active",
            )
            session.add(task)
            await session.flush()
        facts = await self.administration.effective_facts(session, organization_id)
        fact_ids = [
            str(item.revision_id)
            for item in facts
            if item.location_id is None or item.location_id == location_id
        ][:100]
        execution = AIExecution(
            organization_id=organization_id,
            location_id=location_id,
            task_definition_id=task.id,
            workflow_run_id=workflow_run_id,
            idempotency_key=f"agent-run-{workflow_run_id}",
            status="running",
            provider_key="hermes",
            input_references=[str(workflow_run_id)],
            approved_fact_revision_ids=fact_ids,
            requires_human_review=True,
        )
        session.add(execution)
        await session.flush()
        return execution

    @staticmethod
    def _capability_snapshot(
        settings: Settings, capabilities: HermesCapabilities
    ) -> dict[str, object]:
        return {
            "runtime_release": settings.hermes_runtime_release,
            "runtime_version": capabilities.runtime_version,
            "api_model_alias": capabilities.model,
            "model": settings.ai_hermes_model,
            "features": {name: capabilities.supports(name) for name in sorted(REQUIRED_FEATURES)},
            "runtime": {
                "mode": capabilities.runtime.get("mode"),
                "tool_execution": capabilities.runtime.get("tool_execution"),
                "split_runtime": capabilities.runtime.get("split_runtime"),
            },
            "sanctioned_tools": list(capabilities.sanctioned_tools),
        }

    async def _prepare(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        location_id: UUID | None,
        workflow_run_id: UUID,
        skill: AgentSkill,
        capabilities: HermesCapabilities,
        correlation_id: str,
    ) -> tuple[AgentRun, AgentSession]:
        existing = await session.scalar(
            select(AgentRun).where(
                AgentRun.organization_id == organization_id,
                AgentRun.workflow_run_id == workflow_run_id,
            )
        )
        if existing is not None:
            scoped_session = await session.get(AgentSession, existing.agent_session_id)
            if (
                scoped_session is None
                or scoped_session.organization_id != organization_id
                or scoped_session.location_id != location_id
                or scoped_session.skill_key != skill.key
            ):
                raise RuntimeError("agent session binding missing")
            return existing, scoped_session
        scoped_session = await self._session(
            session, settings, organization_id, location_id, skill.key
        )
        active_run = await session.scalar(
            select(AgentRun.id).where(
                AgentRun.organization_id == organization_id,
                AgentRun.agent_session_id == scoped_session.id,
                AgentRun.status.in_(ACTIVE_AGENT_STATUSES),
            )
        )
        if active_run is not None:
            raise HermesRuntimeError(
                "HERMES_SCOPED_SESSION_BUSY",
                "A Hermes run is already active for this organization, location, and skill",
            )
        execution = await self._task_and_execution(
            session, organization_id, location_id, workflow_run_id, skill
        )
        run = AgentRun(
            organization_id=organization_id,
            location_id=location_id,
            workflow_run_id=workflow_run_id,
            ai_execution_id=execution.id,
            agent_session_id=scoped_session.id,
            skill_key=skill.key,
            skill_version=skill.version,
            # Hermes' Runs body session_id owns the durable transcript. The
            # same opaque scoped key is also sent as X-Hermes-Session-Key for
            # long-term memory. A partial unique index permits only one active
            # run per scoped session, so sanctioned tool binding is unambiguous.
            hermes_session_id=scoped_session.hermes_session_key,
            correlation_id=correlation_id,
            status="queued",
            provider_key="hermes",
            model_key=settings.ai_hermes_model,
            capability_snapshot=self._capability_snapshot(settings, capabilities),
            output_references=[],
            source_references=[],
            event_count=0,
        )
        session.add(run)
        await session.flush()
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type="agent.run.created",
                action="agent.run.create",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.WORKFLOW,
                organization_id=organization_id,
                location_id=location_id,
                product_key=skill.product_key,
                resource_type="agent_run",
                resource_id=run.id,
                correlation_id=correlation_id,
                workflow_execution_id=workflow_run_id,
                summary=f"Governed Hermes run created for {skill.key}.",
                metadata={"skill_key": skill.key, "skill_version": skill.version},
            ),
        )
        await session.commit()
        return run, scoped_session

    async def _persist_event(
        self,
        session: AsyncSession,
        settings: Settings,
        run: AgentRun,
        raw_event: dict[str, Any],
    ) -> None:
        document = safe_event_document(raw_event)
        if document is None or run.event_count >= settings.hermes_agent_event_limit:
            return
        event_type = str(raw_event.get("event", "unknown"))[:64]
        timestamp = raw_event.get("timestamp")
        occurred_at = (
            datetime.fromtimestamp(float(timestamp), tz=UTC)
            if isinstance(timestamp, (int, float))
            else datetime.now(UTC)
        )
        await session.execute(
            delete(AgentRunEvent).where(
                AgentRunEvent.organization_id == run.organization_id,
                AgentRunEvent.expires_at <= datetime.now(UTC),
            )
        )
        run.event_count += 1
        session.add(
            AgentRunEvent(
                organization_id=run.organization_id,
                agent_run_id=run.id,
                sequence=run.event_count,
                event_type=event_type,
                event_document=document,
                occurred_at=occurred_at,
                expires_at=datetime.now(UTC)
                + timedelta(days=settings.hermes_agent_event_retention_days),
            )
        )
        if event_type == "approval.request":
            run.status = "waiting_approval"
            run.current_approval = document
        elif event_type == "approval.responded":
            run.status = "running"
            run.current_approval = None
        elif event_type == "run.cancelled":
            run.status = "cancelled"
            run.safe_error_code = None
            run.completed_at = occurred_at
        elif event_type == "run.failed":
            run.status = "failed"
            run.safe_error_code = "HERMES_RUN_FAILED"
            run.completed_at = occurred_at
        elif event_type == "run.completed":
            run.status = "completed"
            run.safe_error_code = None
            run.completed_at = occurred_at
            output = document.get("output")
            run.final_output = {"text": output} if output else {"text": ""}
            raw_usage = document.get("usage")
            usage = cast(dict[str, Any], raw_usage) if isinstance(raw_usage, dict) else {}
            run.input_tokens = usage.get("input_tokens")
            run.output_tokens = usage.get("output_tokens")
        await session.flush()
        await session.commit()

    async def execute_workflow(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        workflow_run_id: UUID,
        workflow_key: str,
        input_document: dict[str, Any],
        correlation_id: str,
    ) -> JobOutcome:
        if settings.ai_provider != "hermes":
            return JobOutcome(result="permanent_failure", safe_error="HERMES_AGENT_NOT_ENABLED")
        if has_secret_key(input_document):
            return JobOutcome(result="permanent_failure", safe_error="AGENT_INPUT_SECRET_REJECTED")
        skill = skill_for_workflow(workflow_key)
        client = self._client_factory(settings)
        try:
            capabilities = await client.capabilities()
        except HermesRuntimeError as exc:
            return JobOutcome(
                result=(
                    "retryable_failure"
                    if exc.safe_code
                    in {"HERMES_TIMEOUT", "HERMES_UNAVAILABLE", "HERMES_HTTP_ERROR"}
                    else "permanent_failure"
                ),
                safe_error=exc.safe_code,
            )
        if capabilities.missing_required:
            return JobOutcome(
                result="permanent_failure", safe_error="HERMES_CAPABILITY_UNAVAILABLE"
            )

        try:
            run, scoped_session = await self._prepare(
                session,
                settings,
                organization_id,
                location_id,
                workflow_run_id,
                skill,
                capabilities,
                correlation_id,
            )
        except HermesRuntimeError as exc:
            return JobOutcome(
                result="retryable_failure"
                if exc.safe_code == "HERMES_SCOPED_SESSION_BUSY"
                else "permanent_failure",
                safe_error=exc.safe_code,
            )
        if run.status == "completed":
            return JobOutcome(result="succeeded", result_reference=f"agent-run:{run.id}")
        objective = redact_text(
            input_document.get("objective")
            or f"Execute the {skill.title} for the bound LILOs scope using current evidence.",
            limit=4_000,
        )
        context_reference = input_document.get("context_reference")
        if context_reference:
            objective += (
                f"\nBound LILOs context reference: {redact_text(context_reference, limit=500)}"
            )
        started = monotonic()
        try:
            if run.hermes_run_id:
                hermes_run_id = run.hermes_run_id
                remote = await client.get_run(hermes_run_id)
                remote_status = str(remote.get("status") or "")
                if remote_status in TERMINAL_HERMES_STATUSES:
                    terminal_event: dict[str, Any] = {
                        "event": f"run.{remote_status}",
                        "timestamp": datetime.now(UTC).timestamp(),
                    }
                    if remote_status == "completed":
                        terminal_event.update(
                            {"output": remote.get("output"), "usage": remote.get("usage", {})}
                        )
                    elif remote_status == "failed":
                        terminal_event["error"] = remote.get("error")
                    await self._persist_event(session, settings, run, terminal_event)
                else:
                    run.status = (
                        "waiting_approval"
                        if remote_status == "waiting_for_approval"
                        else "stopping"
                        if remote_status == "stopping"
                        else "running"
                    )
                    run.safe_error_code = None
                    run.completed_at = None
                    await session.commit()
            else:
                hermes_run_id = await client.create_run(
                    objective=objective,
                    instructions=skill.instructions,
                    hermes_session_id=run.hermes_session_id,
                    session_key=scoped_session.hermes_session_key,
                    model=settings.ai_hermes_model,
                )
                run.hermes_run_id = hermes_run_id
                run.status = "running"
                run.started_at = datetime.now(UTC)
                run.completed_at = None
                await session.commit()
            if run.status not in TERMINAL_HERMES_STATUSES:
                async for event in client.stream_events(hermes_run_id):
                    await self._persist_event(session, settings, run, event)
            await session.refresh(run)
            if run.status not in TERMINAL_HERMES_STATUSES:
                remote = await client.get_run(hermes_run_id)
                remote_status = str(remote.get("status") or "")
                if remote_status in TERMINAL_HERMES_STATUSES:
                    terminal_event = {
                        "event": f"run.{remote_status}",
                        "timestamp": datetime.now(UTC).timestamp(),
                    }
                    if remote_status == "completed":
                        terminal_event.update(
                            {"output": remote.get("output"), "usage": remote.get("usage", {})}
                        )
                    elif remote_status == "failed":
                        terminal_event["error"] = remote.get("error")
                    await self._persist_event(session, settings, run, terminal_event)
                else:
                    raise HermesRuntimeError(
                        "HERMES_EVENT_STREAM_FAILED",
                        "Hermes event stream ended before a terminal event",
                    )
        except HermesRuntimeError as exc:
            reconciled = False
            if run.hermes_run_id:
                try:
                    remote = await client.get_run(run.hermes_run_id)
                    remote_status = str(remote.get("status") or "")
                    if remote_status in TERMINAL_HERMES_STATUSES:
                        synthetic = {
                            "event": f"run.{remote_status}",
                            "timestamp": datetime.now(UTC).timestamp(),
                        }
                        if remote_status == "completed":
                            synthetic.update(
                                {
                                    "output": remote.get("output"),
                                    "usage": remote.get("usage", {}),
                                }
                            )
                        elif remote_status == "failed":
                            synthetic["error"] = remote.get("error")
                        await self._persist_event(session, settings, run, synthetic)
                        reconciled = True
                except HermesRuntimeError:
                    pass
            if not reconciled:
                run.safe_error_code = exc.safe_code
                if run.hermes_run_id and exc.safe_code in {
                    "HERMES_TIMEOUT",
                    "HERMES_UNAVAILABLE",
                    "HERMES_EVENT_STREAM_FAILED",
                }:
                    # The native run identity is known, so the workflow retry
                    # can safely reconnect without creating duplicate work.
                    run.status = "queued"
                    run.completed_at = None
                else:
                    # A failed/ambiguous create has no safe native idempotency
                    # recovery. Disable its tool binding and rotate this
                    # scoped Hermes transcript before any future run.
                    run.status = "failed"
                    run.completed_at = datetime.now(UTC)
                    if not run.hermes_run_id:
                        scoped_session.status = "expired"
                await session.commit()
        finally:
            run.latency_ms = round((monotonic() - started) * 1000)
            execution = (
                await session.get(AIExecution, run.ai_execution_id) if run.ai_execution_id else None
            )
            if execution is not None:
                execution.provider_key = "hermes"
                execution.model_key = run.model_key
                execution.input_tokens = run.input_tokens
                execution.output_tokens = run.output_tokens
                execution.latency_ms = run.latency_ms
                execution.output_document = run.final_output
                execution.output_hash = (
                    hashlib.sha256(
                        json.dumps(run.final_output, sort_keys=True, default=str).encode()
                    ).hexdigest()
                    if run.final_output is not None
                    else None
                )
                execution.status = "completed" if run.status == "completed" else "provider_failed"
                execution.safe_error_code = run.safe_error_code
                execution.completed_at = run.completed_at or datetime.now(UTC)
            await session.commit()

        if run.status == "completed":
            return JobOutcome(result="succeeded", result_reference=f"agent-run:{run.id}")
        if run.status == "cancelled":
            return JobOutcome(result="permanent_failure", safe_error="HERMES_RUN_CANCELLED")
        return JobOutcome(
            result="retryable_failure"
            if run.hermes_run_id
            and run.safe_error_code
            in {"HERMES_TIMEOUT", "HERMES_UNAVAILABLE", "HERMES_EVENT_STREAM_FAILED"}
            else "permanent_failure",
            safe_error=run.safe_error_code or "HERMES_RUN_FAILED",
        )

    async def _scoped_run(
        self, session: AsyncSession, organization_id: UUID, agent_run_id: UUID
    ) -> AgentRun | None:
        result = await session.scalar(
            select(AgentRun).where(
                AgentRun.organization_id == organization_id, AgentRun.id == agent_run_id
            )
        )
        return result if isinstance(result, AgentRun) else None

    async def control(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        agent_run_id: UUID,
        action: str,
        *,
        text: str | None,
        choice: str | None,
        actor_id: UUID,
        correlation_id: str,
    ) -> AgentRun | None:
        run = await self._scoped_run(session, organization_id, agent_run_id)
        if run is None:
            return None
        if not run.hermes_run_id:
            raise ValueError("Hermes run has not started")
        allowed_statuses = {
            "stop": {"running", "waiting_approval"},
            "steer": {"running"},
            "approval": {"waiting_approval"},
        }
        if run.status not in allowed_statuses[action]:
            raise ValueError(f"Hermes run status does not permit {action}")
        if action == "approval" and not run.current_approval:
            raise ValueError("Hermes run has no active approval request")
        feature = {"stop": "run_stop", "steer": "run_steer", "approval": "run_approval_response"}[
            action
        ]
        features = run.capability_snapshot.get("features", {})
        if not isinstance(features, dict) or not features.get(feature):
            raise ValueError(f"Hermes capability unavailable: {feature}")
        client = self._client_factory(settings)
        if action == "stop":
            await client.stop(run.hermes_run_id)
            run.status = "stopping"
        elif action == "steer":
            if not text or not text.strip():
                raise ValueError("steer text is required")
            await client.steer(run.hermes_run_id, text.strip()[:4_000])
        else:
            if choice not in {"once", "deny"}:
                raise ValueError("LILOs permits one-time approval or denial only")
            await client.approve(run.hermes_run_id, choice)
            run.current_approval = None
            run.status = "running"
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=f"agent.run.{action}",
                action=f"agent.run.{action}",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER,
                actor_id=actor_id,
                organization_id=organization_id,
                location_id=run.location_id,
                product_key=run.skill_key.split(".")[0],
                resource_type="agent_run",
                resource_id=run.id,
                correlation_id=correlation_id,
                workflow_execution_id=run.workflow_run_id,
                summary=f"Hermes agent run {action} accepted.",
                metadata={"transport": "hermes_http_runs", "choice": choice}
                if choice
                else {"transport": "hermes_http_runs"},
            ),
        )
        await session.flush()
        return run

    async def list_runs(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        location_id: UUID | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        statement = select(AgentRun).where(AgentRun.organization_id == organization_id)
        if location_id is not None:
            statement = statement.where(AgentRun.location_id == location_id)
        rows = list(
            await session.scalars(statement.order_by(AgentRun.created_at.desc()).limit(limit))
        )
        return [self._summary(row) for row in rows]

    async def detail(
        self, session: AsyncSession, organization_id: UUID, agent_run_id: UUID
    ) -> dict[str, object] | None:
        run = await self._scoped_run(session, organization_id, agent_run_id)
        if run is None:
            return None
        events = list(
            await session.scalars(
                select(AgentRunEvent)
                .where(
                    AgentRunEvent.organization_id == organization_id,
                    AgentRunEvent.agent_run_id == agent_run_id,
                    AgentRunEvent.expires_at > datetime.now(UTC),
                )
                .order_by(AgentRunEvent.sequence)
            )
        )
        return {
            **self._summary(run),
            "workflow_run_id": str(run.workflow_run_id),
            "ai_execution_id": str(run.ai_execution_id) if run.ai_execution_id else None,
            "hermes_run_id": run.hermes_run_id,
            "hermes_session_id": run.hermes_session_id,
            "audit_correlation_id": run.correlation_id,
            "skill_version": run.skill_version,
            "provider": run.provider_key,
            "capabilities": run.capability_snapshot,
            "current_approval": run.current_approval,
            "source_references": run.source_references,
            "output_references": run.output_references,
            "final_output": run.final_output,
            "usage": {
                "input_tokens": run.input_tokens,
                "output_tokens": run.output_tokens,
                "estimated_cost_microunits": run.estimated_cost_microunits,
                "latency_ms": run.latency_ms,
            },
            "events": [
                {
                    "sequence": event.sequence,
                    "event_type": event.event_type,
                    "event_document": event.event_document,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in events
            ],
        }

    @staticmethod
    def _summary(run: AgentRun) -> dict[str, object]:
        return {
            "id": str(run.id),
            "location_id": str(run.location_id) if run.location_id else None,
            "skill_key": run.skill_key,
            "status": run.status,
            "model": run.model_key,
            "safe_error_code": run.safe_error_code,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
