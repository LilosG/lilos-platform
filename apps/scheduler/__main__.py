"""Production durable-scheduler process entrypoint."""

import asyncio

from apps.api.app.execution.runtime import process_main, run_scheduler


def main() -> int:
    """Run until a termination signal or a fail-closed runtime failure."""
    return asyncio.run(process_main("lilos-scheduler", run_scheduler))


if __name__ == "__main__":
    raise SystemExit(main())
