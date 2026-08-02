import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run async database tests on asyncio, which is required by asyncpg."""
    return "asyncio"
