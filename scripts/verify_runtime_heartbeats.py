"""Read-only, production-safe verification of worker/scheduler heartbeat freshness.

Confirms that ``lilos-worker`` and ``lilos-scheduler`` each have a recent
persisted heartbeat in the existing ``service_heartbeats`` table (written by
``apps.api.app.execution.runtime.DurableProcessBackend.heartbeat``), with no
stale or duplicate active runtime identity. This script performs SELECT-only
queries — it creates, updates, or deletes no records — and is never mounted
as an HTTP route.

Run manually with direct read access to the target database
(``LILOS_DATABASE_URL`` already present in the process environment), for
example as a Render one-off Job on the ``lilos-api`` service, which already
carries that configuration:

    render jobs create srv-d9oi90ad0e5s73bldhng \\
      --start-command "python -m scripts.verify_runtime_heartbeats"

Optional environment variables (never logged or printed):
    HEARTBEAT_SERVICES            Comma-separated service names to check.
                                   Default: lilos-worker,lilos-scheduler
    HEARTBEAT_ENVIRONMENT         Expected ``environment`` column value.
                                   Default: this process's own LILOS_ENV
                                   (typically "production" when run on
                                   Render alongside the API/worker/scheduler).
    HEARTBEAT_MAX_AGE_SECONDS     Freshness window in seconds. Default: 120
                                   (8x the runtime's default 15s heartbeat
                                   interval, allowing for one or two missed
                                   cycles without a false failure).
    HEARTBEAT_EXPECTED_RELEASE    If set, the most recent heartbeat's
                                   ``release`` must match exactly (e.g. the
                                   deployed commit SHA).

Only non-secret identity/timing fields are printed: service name, instance
key (already documented as a bounded non-secret identity in
``execution/runtime.py``), release, status, and heartbeat age. No database
credentials, tokens, or raw environment values are ever printed.

Exit status is 0 only when every checked service has exactly one recent,
non-stale, non-duplicate active heartbeat matching its expected identity;
otherwise 1.
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.observability.models import ServiceHeartbeat

DEFAULT_SERVICES: tuple[str, ...] = ("lilos-worker", "lilos-scheduler")
DEFAULT_MAX_AGE_SECONDS = 120.0


@dataclass(frozen=True, slots=True)
class HeartbeatCheck:
    service: str
    ok: bool
    reason: str | None
    instance_key: str | None
    release: str | None
    status: str | None
    age_seconds: float | None
    active_row_count: int


def _services() -> tuple[str, ...]:
    raw = os.environ.get("HEARTBEAT_SERVICES", "").strip()
    if not raw:
        return DEFAULT_SERVICES
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _max_age_seconds() -> float:
    raw = os.environ.get("HEARTBEAT_MAX_AGE_SECONDS", "").strip()
    if not raw:
        return DEFAULT_MAX_AGE_SECONDS
    try:
        value = float(raw)
    except ValueError:
        raise SystemExit(
            "verification blocked: HEARTBEAT_MAX_AGE_SECONDS must be numeric"
        ) from None
    if value <= 0:
        raise SystemExit("verification blocked: HEARTBEAT_MAX_AGE_SECONDS must be positive")
    return value


async def check_service(
    session: AsyncSession,
    *,
    environment: str,
    service: str,
    max_age_seconds: float,
    expected_release: str | None,
) -> HeartbeatCheck:
    rows = list(
        await session.scalars(
            select(ServiceHeartbeat)
            .where(
                ServiceHeartbeat.environment == environment,
                ServiceHeartbeat.service == service,
            )
            .order_by(ServiceHeartbeat.last_seen_at.desc())
        )
    )
    if not rows:
        return HeartbeatCheck(service, False, "no heartbeat found", None, None, None, None, 0)

    now = datetime.now(UTC)
    latest = rows[0]
    age = (now - latest.last_seen_at).total_seconds()
    active = [row for row in rows if (now - row.last_seen_at).total_seconds() <= max_age_seconds]

    if len(active) > 1:
        return HeartbeatCheck(
            service,
            False,
            f"duplicate active runtime identity ({len(active)} instances heartbeating)",
            latest.instance_key,
            latest.release,
            latest.status,
            age,
            len(active),
        )
    if age > max_age_seconds:
        return HeartbeatCheck(
            service,
            False,
            f"stale heartbeat ({age:.1f}s old, limit {max_age_seconds:.0f}s)",
            latest.instance_key,
            latest.release,
            latest.status,
            age,
            len(active),
        )
    if latest.status != "running":
        return HeartbeatCheck(
            service,
            False,
            f"unexpected status '{latest.status}'",
            latest.instance_key,
            latest.release,
            latest.status,
            age,
            len(active),
        )
    if expected_release is not None and latest.release != expected_release:
        return HeartbeatCheck(
            service,
            False,
            "release does not match HEARTBEAT_EXPECTED_RELEASE",
            latest.instance_key,
            latest.release,
            latest.status,
            age,
            len(active),
        )
    return HeartbeatCheck(
        service, True, None, latest.instance_key, latest.release, latest.status, age, len(active)
    )


def _print_result(result: HeartbeatCheck) -> None:
    age_text = f"{result.age_seconds:.1f}" if result.age_seconds is not None else "none"
    summary = (
        f"service={result.service} ok={result.ok} "
        f"instance_key={result.instance_key or 'none'} release={result.release or 'none'} "
        f"status={result.status or 'none'} age_seconds={age_text} "
        f"active_row_count={result.active_row_count}"
    )
    if not result.ok:
        summary += f" reason={result.reason}"
    print(summary)


async def verify() -> int:
    services = _services()
    max_age_seconds = _max_age_seconds()
    expected_release = os.environ.get("HEARTBEAT_EXPECTED_RELEASE", "").strip() or None
    settings = Settings()
    environment = os.environ.get("HEARTBEAT_ENVIRONMENT", "").strip() or settings.environment.value

    runtime = create_database_runtime(settings)
    session_factory = runtime.require_session_factory()
    results: list[HeartbeatCheck] = []
    try:
        async with session_factory() as session:
            for service in services:
                results.append(
                    await check_service(
                        session,
                        environment=environment,
                        service=service,
                        max_age_seconds=max_age_seconds,
                        expected_release=expected_release,
                    )
                )
    finally:
        await runtime.dispose()

    for result in results:
        _print_result(result)

    if all(result.ok for result in results):
        print("Runtime heartbeat verification passed for all services.")
        return 0
    print("Runtime heartbeat verification FAILED for one or more services.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(verify()))
