"""Production durable-scheduler process entrypoint."""

import asyncio
import logging

from apps.api.app.config import Settings
from apps.api.app.execution.runtime import (
    RuntimeOptions,
    SchedulerBackend,
    process_main,
    run_process,
)
from apps.api.app.growth.lifecycle import GrowthLifecycleService
from apps.api.app.observability.telemetry import MetricPoint

logger = logging.getLogger("lilos")


class PlatformSchedulerBackend(SchedulerBackend):
    """Extend the canonical scheduler with cross-product Growth reconciliation."""

    def __init__(self, settings: Settings, options: RuntimeOptions) -> None:
        super().__init__(settings, options)
        self.growth_lifecycle = GrowthLifecycleService()

    async def sweep(self) -> None:
        """Advance Growth inside the existing durable scheduler reconciliation hook."""
        await super().sweep()
        async with self.sessions() as session, session.begin():
            result = await self.growth_lifecycle.advance_batch(
                session,
                limit=self.options.sweep_batch_size,
            )
        MetricPoint.create(
            "growth.lifecycle.reconciled",
            result.reconciled,
            {
                "service": self.service_name,
                "operation": "growth_reconcile",
                "outcome": "success",
            },
        )
        if result.scanned:
            logger.info(
                "Growth lifecycle reconciliation completed",
                extra={
                    "event_name": "scheduler.growth.reconciled",
                    "operation": "growth_reconcile",
                    "outcome": "success",
                    "scanned": result.scanned,
                    "reconciled": result.reconciled,
                    "dispatched": result.dispatched,
                },
            )


async def run_platform_scheduler(settings: Settings, stop: asyncio.Event) -> None:
    """Run schedule dispatch and Growth lifecycle reconciliation in one process plane."""
    options = RuntimeOptions(shutdown_seconds=45.0, cycle_seconds=45.0)
    await run_process(PlatformSchedulerBackend(settings, options), stop)


def main() -> int:
    """Run until a termination signal or a fail-closed runtime failure."""
    return asyncio.run(process_main("lilos-scheduler", run_platform_scheduler))


if __name__ == "__main__":
    raise SystemExit(main())
