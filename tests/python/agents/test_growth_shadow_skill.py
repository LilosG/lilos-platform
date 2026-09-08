"""Safety contract for the first read-only Growth planner."""

from apps.api.app.agents.skills import SKILLS, skill_for_workflow
from apps.api.app.agents.tools import TOOL_SPECS
from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES


def test_growth_workflow_maps_to_cross_product_shadow_skill() -> None:
    skill = skill_for_workflow("agent.growth")

    assert skill is SKILLS["growth.operator"]
    assert skill.product_key == "growth"
    assert skill.version == 1
    assert WORKFLOW_TYPES["agent.growth"][1] == "growth"


def test_growth_shadow_skill_has_no_mutating_tools() -> None:
    skill = SKILLS["growth.operator"]

    assert skill.required_tools
    assert all(tool_name in TOOL_SPECS for tool_name in skill.required_tools)
    assert all(not TOOL_SPECS[tool_name].mutating for tool_name in skill.required_tools)
    assert "analyze_seo_opportunities" not in skill.required_tools
    assert "run_site_crawl" not in skill.required_tools
    assert "submit_for_approval" not in skill.required_tools
