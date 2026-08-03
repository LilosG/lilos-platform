"""Production durable-worker process entrypoint."""

import asyncio

from apps.api.app.execution.runtime import process_main, run_worker


def main() -> int:
    """Run until a termination signal or a fail-closed runtime failure."""
    return asyncio.run(process_main("lilos-worker", run_worker))


if __name__ == "__main__":
    raise SystemExit(main())
