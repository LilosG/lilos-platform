"""The schema Hermes advertises must match the arguments LILOs accepts.

These live in two places. The agent learns a tool's parameters from
``infrastructure/hermes/plugins/lilos``, which is baked into the Hermes image;
the server validates them against ``TOOL_SPECS``. Nothing tied the two together,
so narrowing ``TOOL_SPECS`` for ``generate_gbp_post_proposal`` without editing the
plugin left the agent sending ``content`` and ``post_type`` -- fields its own
schema declared required -- and the server rejecting them with
``HERMES_TOOL_DENIED``. The agent's report named it exactly: "its enforced runtime
schema requires post_type and content, but the tool returns HERMES_TOOL_DENIED for
exactly those arguments, making a valid write impossible."

That divergence is invisible at build time and only appears on a live run against
a real client, so it is asserted here instead.
"""

import ast
import pathlib
from types import SimpleNamespace
from typing import Any

import pytest

from apps.api.app.agents.tools import TOOL_SPECS

PLUGIN_PATH = (
    pathlib.Path(__file__).resolve().parents[3] / "infrastructure/hermes/plugins/lilos/__init__.py"
)

_DECLARATIONS = frozenset(
    {"_object", "STRING", "STRINGS", "OBJECT", "OBJECTS", "SCHEMAS", "DESCRIPTIONS"}
)


def _load_plugin() -> Any:
    """Evaluate the plugin's schema tables without importing the module.

    The plugin imports the Hermes ``gateway`` runtime, which exists only inside the
    Hermes image, so a normal import fails here. Its schema tables are module-level
    literals built from one helper and a few constants, so those declarations are
    lifted out of the AST and evaluated alone in an empty namespace.
    """
    assert PLUGIN_PATH.exists(), f"Hermes plugin not found at {PLUGIN_PATH}"
    tree = ast.parse(PLUGIN_PATH.read_text(encoding="utf-8"))
    kept: list[ast.stmt] = []
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name in _DECLARATIONS
            or isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id in _DECLARATIONS
                for target in node.targets
            )
        ):
            kept.append(node)
    namespace: dict[str, Any] = {}
    exec(compile(ast.Module(body=kept, type_ignores=[]), str(PLUGIN_PATH), "exec"), namespace)
    for name in ("SCHEMAS", "DESCRIPTIONS"):
        assert name in namespace, f"{name} was not found in the plugin"
    return SimpleNamespace(SCHEMAS=namespace["SCHEMAS"], DESCRIPTIONS=namespace["DESCRIPTIONS"])


@pytest.fixture(scope="module")
def plugin() -> Any:
    return _load_plugin()


def test_plugin_and_server_expose_the_same_tools(plugin: Any) -> None:
    assert set(plugin.SCHEMAS) == set(TOOL_SPECS)
    assert set(plugin.DESCRIPTIONS) == set(TOOL_SPECS)


def test_advertised_properties_never_exceed_accepted_arguments(plugin: Any) -> None:
    """A property the server refuses makes the tool uncallable as advertised."""
    for name, schema in plugin.SCHEMAS.items():
        advertised = set(schema["properties"])
        accepted = set(TOOL_SPECS[name].allowed_arguments)
        unusable = advertised - accepted
        assert not unusable, (
            f"{name} advertises arguments the server rejects: {sorted(unusable)}. "
            "The agent will send them and receive HERMES_TOOL_DENIED."
        )


def test_required_arguments_are_all_accepted(plugin: Any) -> None:
    """A required argument the server refuses makes every valid call impossible."""
    for name, schema in plugin.SCHEMAS.items():
        required = set(schema.get("required") or ())
        accepted = set(TOOL_SPECS[name].allowed_arguments)
        impossible = required - accepted
        assert not impossible, f"{name} requires arguments the server rejects: {sorted(impossible)}"


def test_accepted_arguments_are_all_advertised(plugin: Any) -> None:
    """An accepted argument the agent is never told about cannot be used."""
    for name, spec in TOOL_SPECS.items():
        advertised = set(plugin.SCHEMAS[name]["properties"])
        unreachable = set(spec.allowed_arguments) - advertised
        assert not unreachable, (
            f"{name} accepts arguments absent from the advertised schema: {sorted(unreachable)}"
        )


def test_gbp_post_proposal_takes_evidence_not_copy(plugin: Any) -> None:
    """Regression for the failed Wheyland run: copy is not an agent argument."""
    schema = plugin.SCHEMAS["generate_gbp_post_proposal"]

    assert set(schema["properties"]) == {"source_evidence_references", "review_id"}
    assert schema["required"] == ["source_evidence_references"]
    for rejected in ("content", "post_type", "call_to_action"):
        assert rejected not in schema["properties"]


def test_schemas_forbid_unknown_properties(plugin: Any) -> None:
    """additionalProperties must stay closed so the agent cannot invent fields."""
    for name, schema in plugin.SCHEMAS.items():
        assert schema.get("additionalProperties") is False, name
