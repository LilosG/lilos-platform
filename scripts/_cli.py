"""Shared entrypoint for the scripts an operator runs from the Render shell.

The Render shell has no `uv`, so these are run as

    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.<name> <args>

`run_script` turns the two failures an operator can actually cause -- forgetting
`LILOS_RELEASE`, or a Google connection that needs reconnecting -- into a single
clear line and a distinct exit code instead of a traceback, and does the same for
any other expected application error. Genuine bugs still raise.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import InterfaceError, OperationalError

from apps.api.app.errors import ApiError
from apps.api.app.integrations.errors import IntegrationReconnectRequiredError

EXIT_BAD_ENVIRONMENT = 2
EXIT_RECONNECT_REQUIRED = 3
EXIT_EXPECTED_ERROR = 1


def _fail(message: str, code: int) -> int:
    print(f"error: {message}", file=sys.stderr)
    return code


def run_script(name: str, main: Callable[[], Coroutine[Any, Any, int]]) -> int:
    """Run ``main`` and return the process exit code. Never prints a traceback for
    a missing release id, a reconnect-required connection, or a known app error."""
    if not os.environ.get("LILOS_RELEASE", "").strip():
        return _fail(
            "LILOS_RELEASE is not set. Run it as: "
            f'LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.{name} <args>',
            EXIT_BAD_ENVIRONMENT,
        )
    try:
        return asyncio.run(main())
    except IntegrationReconnectRequiredError:
        return _fail(
            "a Google connection needs to be reconnected (INTEGRATION_RECONNECT_REQUIRED). "
            "Reconnect it in Integrations, then run this again.",
            EXIT_RECONNECT_REQUIRED,
        )
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "settings"
        return _fail(f"invalid configuration: {where}: {first['msg']}", EXIT_BAD_ENVIRONMENT)
    except (OSError, OperationalError, InterfaceError) as exc:
        # Connectivity only -- an integrity or programming error is a bug and still raises.
        return _fail(
            f"the database could not be reached ({type(exc).__name__}). "
            "Check the service is up and its connection settings, then run this again.",
            EXIT_EXPECTED_ERROR,
        )
    except ApiError as exc:
        return _fail(f"{exc.code}: {exc.public_message}", EXIT_EXPECTED_ERROR)
