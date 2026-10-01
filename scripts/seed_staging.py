"""Explicit staging-only seed command: python -m scripts.seed_staging."""

import asyncio

# Register the same canonical model graph as the worker before service use.
import apps.worker.bootstrap  # noqa: F401
from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.staging.seed import require_seed_environment, seed_staging


async def main() -> None:
    settings = Settings()
    require_seed_environment(settings)
    runtime = create_database_runtime(settings)
    try:
        async with runtime.require_session_factory().begin() as session:
            ids = await seed_staging(session, settings)
        print("Synthetic staging organizations:", ids)
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    asyncio.run(main())
