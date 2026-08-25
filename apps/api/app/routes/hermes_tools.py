"""Private, service-authenticated sanctioned tool surface for Hermes."""

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.agents.tools import AgentToolDeniedError, AgentToolService
from apps.api.app.config import Settings
from apps.api.app.database.session import get_database_session
from apps.api.app.products.gbp.proposal_enrichment import GBPProposalEnrichmentError

router = APIRouter(prefix="/api/internal/hermes", tags=["hermes-internal"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
tools = AgentToolService()


class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    arguments: dict[str, Any] = Field(default_factory=dict)


def _authenticate(settings: Settings, authorization: str | None) -> None:
    expected = settings.hermes_tool_api_key
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=401, detail="Hermes tool authentication required")


@router.post("/tools/{tool_name}", response_model=None)
async def invoke_tool(
    request: Request,
    tool_name: str,
    command: ToolInvocation,
    session: Session,
    authorization: Annotated[str | None, Header()] = None,
    x_lilos_hermes_session: Annotated[str | None, Header()] = None,
) -> dict[str, object] | JSONResponse:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise HTTPException(status_code=503, detail="Runtime configuration unavailable")
    _authenticate(settings, authorization)
    if not x_lilos_hermes_session or len(x_lilos_hermes_session) > 128:
        raise HTTPException(status_code=403, detail="Bound Hermes session required")
    try:
        run = await tools.bound_run(session, x_lilos_hermes_session)
        result = await tools.invoke(session, run, tool_name, command.arguments)
    except AgentToolDeniedError as exc:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "HERMES_TOOL_DENIED", "message": str(exc)}},
        )
    except GBPProposalEnrichmentError as exc:
        return JSONResponse(
            status_code=502,
            content={"error": {"code": exc.safe_code, "message": str(exc)}},
        )
    except Exception:
        # AgentToolService records a safe failed audit event before raising.
        # Keep provider/runtime internals out of the response.
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "HERMES_TOOL_FAILED",
                    "message": "Sanctioned tool execution failed",
                }
            },
        )
    return {"data": result}
