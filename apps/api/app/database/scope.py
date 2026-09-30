"""Short, self-contained database transactions for code that also talks to providers.

A provider request can take seconds and may hang. Holding a database transaction
open across one pins a connection, holds row locks and can starve the pool, so
sync code must read, close, call the provider with nothing open, then open a new
transaction to persist. `TransactionScope` is what such code is handed instead of
a session: each `begin()` is one short transaction. An `async_sessionmaker` is one.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class TransactionScope(Protocol):
    def begin(self) -> AbstractAsyncContextManager[AsyncSession]: ...
