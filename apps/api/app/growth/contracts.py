from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GrowthActionCreate(BaseModel):
    """One typed action in a cross-product growth initiative."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_key: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    product_key: str = Field(min_length=1, max_length=64)
    action_type: str = Field(min_length=1, max_length=64)
    target_reference: str = Field(min_length=1, max_length=1000)
    executor_workflow_key: str | None = Field(default=None, min_length=1, max_length=128)
    dependency_keys: list[str] = Field(default_factory=list, max_length=20)
    evidence_references: list[str] = Field(min_length=1, max_length=100)
    expected_result_hypothesis: str = Field(min_length=1, max_length=2000)
    verification_plan: dict[str, object] = Field(default_factory=dict)
    risk: Literal["low", "medium", "high"]
    effort: Literal["low", "medium", "high"]
    approval_required: bool = True


class GrowthPlanCreate(BaseModel):
    """A governed cross-product plan created from evidence observed by one Hermes run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    objective: str = Field(min_length=1, max_length=2000)
    rationale: str = Field(min_length=1, max_length=5000)
    source_references: list[str] = Field(min_length=1, max_length=200)
    priority_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    actions: list[GrowthActionCreate] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_action_graph(self) -> GrowthPlanCreate:
        keys = [action.action_key for action in self.actions]
        if len(keys) != len(set(keys)):
            raise ValueError("growth action keys must be unique within a plan")

        known = set(keys)
        graph: dict[str, set[str]] = {}
        for action in self.actions:
            dependencies = set(action.dependency_keys)
            if action.action_key in dependencies:
                raise ValueError("growth action cannot depend on itself")
            missing = dependencies - known
            if missing:
                raise ValueError(
                    "growth action dependencies must reference actions in the same plan: "
                    + ", ".join(sorted(missing))
                )
            graph[action.action_key] = dependencies

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(key: str) -> None:
            if key in visited:
                return
            if key in visiting:
                raise ValueError("growth action dependency graph must be acyclic")
            visiting.add(key)
            for dependency in graph[key]:
                visit(dependency)
            visiting.remove(key)
            visited.add(key)

        for key in keys:
            visit(key)
        return self


class GrowthInitiativeDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    approve: bool


class GrowthActionOutcomeRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    classification: Literal["improved", "unchanged", "regressed", "inconclusive"]
    baseline: dict[str, object] = Field(default_factory=dict)
    measurement: dict[str, object] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list, max_length=20)
