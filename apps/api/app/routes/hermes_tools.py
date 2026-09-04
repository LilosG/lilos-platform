"""Private, service-authenticated sanctioned tool surface for Hermes."""

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.agents.tools import AgentToolDeniedError, AgentToolService
from apps.api.app.config import Settings
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import ApiError
from apps.api.app.products.gbp.capability_backfill import (
    ensure_capability_snapshot_from_profile,
)
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


def _tool_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code[:96], "message": message[:500]}},
    )


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
        if tool_name == "create_gbp_optimization_proposal":
            # Production locations that were synced before capability snapshots
            # became automatic can still have a valid provider profile but no
            # operations capability row. Repair that legacy state from persisted
            # Google truth before the governed proposal path runs. This never
            # contacts Google and cannot grant fields outside adapter support.
            await ensure_capability_snapshot_from_profile(
                session,
                organization_id=run.organization_id,
                location_id=run.location_id,
                correlation_id=run.correlation_id,
            )
        result = await tools.invoke(session, run, tool_name, command.arguments)
    except AgentToolDeniedError as exc:
        return _tool_error(403, "HERMES_TOOL_DENIED", str(exc))
    except GBPProposalEnrichmentError as exc:
        return _tool_error(502, exc.safe_code, str(exc))
    except ApiError as exc:
        # Deliberate domain errors already carry a safe public contract. Hermes
        # must see that code instead of losing it behind HERMES_TOOL_FAILED;
        # otherwise the agent cannot report or act on the real blocker.
        return _tool_error(int(exc.status_code), exc.code, exc.public_message)
    except ValidationError:
        # Tool schemas should keep model arguments valid, but fail closed with a
        # stable safe code if a domain contract rejects them.
        return _tool_error(
            422,
            "HERMES_TOOL_ARGUMENT_INVALID",
            "The sanctioned tool arguments did not pass the LILOs domain contract.",
        )
    except Exception:
        # AgentToolService records a safe failed audit event before raising.
        # Keep provider/runtime internals out of the response.
        return _tool_error(502, "HERMES_TOOL_FAILED", "Sanctioned tool execution failed")
    return {"data": result}
