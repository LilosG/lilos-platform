"""Install read-only schedules after independent OAuth and mapping acceptance."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import apps.worker.bootstrap  # noqa: F401
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.execution.contracts import ScheduleCreate
from apps.api.app.execution.models import Schedule
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.seo.models import SEOSearchProperty


async def configure(session: AsyncSession, settings: Settings) -> int:
    if (
        settings.environment is not EnvironmentName.STAGING
        or not settings.staging_live_google_organization_ids
    ):
        raise ValueError("Read smoke requires explicitly authorized staging organizations")
    created = 0
    for raw_id in settings.staging_live_google_organization_ids.split(","):
        organization_id = UUID(raw_id)
        providers: tuple[tuple[str, type[SEOSearchProperty] | type[AnalyticsProperty]], ...] = (
            ("seo.sync_search_console", SEOSearchProperty),
            ("insights.sync_analytics", AnalyticsProperty),
        )
        for key, model in providers:
            connection_ids = list(
                await session.scalars(
                    select(model.connection_id).where(
                        model.organization_id == organization_id, model.mapping_status == "mapped"
                    )
                )
            )
            if len(connection_ids) != 1:
                raise ValueError("Smoke requires exactly one confirmed mapping per provider")
            connection = await session.get(IntegrationConnection, connection_ids[0])
            if (
                connection is None
                or connection.status != "connected"
                or not connection.credential_reference
                or connection.credential_reference.startswith("fixture:")
            ):
                raise ValueError("Smoke requires independently authorized live staging credentials")
            schedule_key = f"staging-smoke-{key}"
            existing = await session.scalar(
                select(Schedule).where(
                    Schedule.organization_id == organization_id, Schedule.key == schedule_key
                )
            )
            if existing is None:
                await ExecutionService().create_schedule(
                    session,
                    organization_id,
                    ScheduleCreate(
                        workflow_key=key,
                        key=schedule_key,
                        cron_expression="17 9 * * *",
                        timezone="UTC",
                        next_run_at=datetime.now(UTC),
                    ),
                    correlation_id="staging-smoke-setup",
                )
                created += 1
    return created


async def main() -> None:
    settings = Settings()
    if settings.environment is not EnvironmentName.STAGING:
        raise ValueError("Smoke setup refuses production")
    runtime = create_database_runtime(settings)
    try:
        async with runtime.require_session_factory().begin() as session:
            count = await configure(session, settings)
        print(f"Read-only smoke schedules created: {count}")
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    asyncio.run(main())
