"""Safe worker entrypoint for the Phase 0 process baseline."""

import json


def main() -> int:
    """Report the intentionally idle state and exit successfully."""
    print(
        json.dumps(
            {
                "service": "lilos-worker",
                "status": "idle",
                "reason": "No job execution is configured in Roadmap Phase 0.",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
