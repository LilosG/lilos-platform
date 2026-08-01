from collections.abc import Generator
from typing import NoReturn

import pytest
from pydantic import BaseModel, Field
from starlette.testclient import TestClient

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.context import current_correlation_id
from apps.api.app.errors import AuthorizationError, ConflictError, NotFoundError
from apps.api.app.main import create_app


class ValidationProbe(BaseModel):
    name: str = Field(min_length=3, max_length=20)


@pytest.fixture
def client() -> Generator[TestClient]:
    settings = Settings(environment=EnvironmentName.TEST)
    test_app = create_app(settings)

    @test_app.post("/_test/validate")
    async def validation_probe(payload: ValidationProbe) -> dict[str, str]:
        return {"name": payload.name}

    @test_app.get("/_test/context")
    async def context_probe() -> dict[str, str | None]:
        return {"correlation_id": current_correlation_id()}

    @test_app.get("/_test/not-found", response_model=None)
    async def not_found_probe() -> NoReturn:
        raise NotFoundError

    @test_app.get("/_test/authorization", response_model=None)
    async def authorization_probe() -> NoReturn:
        raise AuthorizationError

    @test_app.get("/_test/conflict", response_model=None)
    async def conflict_probe() -> NoReturn:
        raise ConflictError

    @test_app.get("/_test/unexpected", response_model=None)
    async def unexpected_probe() -> NoReturn:
        raise RuntimeError("internal-value-must-not-leak")

    with TestClient(test_app, raise_server_exceptions=False) as test_client:
        yield test_client
