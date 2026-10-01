"""Read tools are open to every bound skill; write tools stay on skill allowlists."""

from types import SimpleNamespace
from typing import cast

import pytest

from apps.api.app.agents.models import AgentRun
from apps.api.app.agents.skills import SKILLS
from apps.api.app.agents.tools import TOOL_SPECS, AgentToolDeniedError, AgentToolService, ToolAccess

SHARED_READ_TOOLS = (
    "read_cross_product_summary",
    "read_client_business_facts",
    "inspect_workflow",
    "read_website_knowledge",
)


def _run(skill_key: str) -> AgentRun:
    return cast(AgentRun, SimpleNamespace(skill_key=skill_key))


@pytest.mark.parametrize("skill_key", sorted(SKILLS))
@pytest.mark.parametrize("tool_name", SHARED_READ_TOOLS)
def test_every_bound_skill_can_call_the_shared_read_tools(skill_key: str, tool_name: str) -> None:
    assert TOOL_SPECS[tool_name].access is ToolAccess.READ
    AgentToolService._validate_skill_tool(_run(skill_key), tool_name)


@pytest.mark.parametrize("skill_key", sorted(SKILLS))
def test_every_read_tool_is_open_to_every_bound_skill(skill_key: str) -> None:
    for name, spec in TOOL_SPECS.items():
        if spec.access is ToolAccess.READ:
            AgentToolService._validate_skill_tool(_run(skill_key), name)


@pytest.mark.parametrize("skill_key", sorted(SKILLS))
def test_write_tools_outside_the_skill_allowlist_are_still_denied(skill_key: str) -> None:
    skill = SKILLS[skill_key]
    outside = [
        name
        for name, spec in TOOL_SPECS.items()
        if spec.access is ToolAccess.WRITE and name not in skill.required_tools
    ]
    assert outside, "every skill should be denied at least one write tool"
    for name in outside:
        with pytest.raises(AgentToolDeniedError, match="not sanctioned"):
            AgentToolService._validate_skill_tool(_run(skill_key), name)
    for name in skill.required_tools:
        AgentToolService._validate_skill_tool(_run(skill_key), name)


def test_unknown_skill_is_still_refused() -> None:
    with pytest.raises(AgentToolDeniedError):
        AgentToolService._validate_skill_tool(_run("nope.operator"), "read_gbp_state")
