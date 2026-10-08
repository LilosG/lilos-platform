"""The Automations rules: attention, failure-code coverage, frequency and the run-now allowlist."""

import ast
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from apps.api.app.execution.automations import (
    FAILURE_POLICY,
    RUN_NOW_WORKFLOWS,
    AutomationReason,
    AutomationStatus,
    FrequencyKind,
    RunOutcome,
    RunSnapshot,
    RunStatus,
    Treatment,
    attention_of,
    known_workflow_keys,
    outcome_of,
    parse_frequency,
    reason_of,
    source_of,
    status_of,
)
from apps.api.app.products.gbp.performance_enums import GBPPerformanceFailureCode
from apps.api.app.routes.command_center_automations import WorkflowTypeCode

EXECUTION = Path(__file__).resolve().parents[3] / "apps/api/app/execution"
SCHEDULED_HANDLERS = {
    "handlers.py": {"_handle_gbp_sync", "_handle_reviews_ingest"},
    "provider_sync_handlers.py": {
        "handle_search_console_sync",
        "_sync_search_property",
        "_sync_analytics_property",
        "handle_analytics_sync",
        "handle_gbp_performance_sync",
    },
    "operational_extensions.py": {
        "_handle_seo_crawl_and_analysis",
        "_crawl_then_analyze",
        "_analyze_website",
        "_handle_gbp_generate_post",
    },
}
# Codes set outside the handler bodies above.
OTHER_CODES = {
    "GBP_WEBSITE_KNOWLEDGE_UNAVAILABLE",
    "GBP_DRIVE_MEDIA_UNAVAILABLE",
    "GBP_DRIVE_MEDIA_PROXY_UNAVAILABLE",
    "GBP_DRIVE_UNREACHABLE",
    "GBP_DRIVE_TEMPORARILY_UNAVAILABLE",
    "GBP_DRIVE_MEDIA_NOT_CONFIGURED",
    "GBP_DRIVE_NO_ELIGIBLE_IMAGE",
    "GBP_ORGANIZATION_UNAVAILABLE",
    "GBP_POST_REVISION_UNAVAILABLE",
    "GBP_WEBSITE_TARGET_UNAVAILABLE",
    "WORKFLOW_VERSION_NOT_EXECUTABLE",
    "WORKFLOW_HANDLER_NOT_REGISTERED",
    "WORKFLOW_RUN_MISSING",
    "WORKFLOW_CANCELLED",
    "HANDLER_EXCEPTION",
    "DATABASE_DETERMINISTIC_ERROR",
    "HERMES_SCOPED_SESSION_BUSY",
    "VERIFICATION_CONTENT_PENDING",
    "VERIFICATION_REREAD_FAILED",
}


def codes_set_by_scheduled_handlers() -> set[str]:
    found: set[str] = set()

    def strings(node: ast.expr) -> list[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.IfExp):
            return strings(node.body) + strings(node.orelse)
        return []

    for filename, functions in SCHEDULED_HANDLERS.items():
        tree = ast.parse((EXECUTION / filename).read_text())
        for function in ast.walk(tree):
            if not isinstance(function, ast.AsyncFunctionDef) or function.name not in functions:
                continue
            for node in ast.walk(function):
                if isinstance(node, ast.keyword) and node.arg == "safe_error":
                    found.update(strings(node.value))
                if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "code" for t in node.targets
                ):
                    found.update(strings(node.value))
    return {code for code in found if code.isupper()}


def test_every_known_reason_has_a_policy() -> None:
    missing = set(AutomationReason) - set(FAILURE_POLICY) - {AutomationReason.UNMAPPED}
    assert not missing, f"failure codes without a mapping: {sorted(missing)}"
    assert AutomationReason.UNMAPPED not in FAILURE_POLICY


def test_every_code_the_scheduled_workflows_set_is_mapped() -> None:
    expected = (
        codes_set_by_scheduled_handlers()
        | {code.value for code in GBPPerformanceFailureCode}
        | OTHER_CODES
    )
    assert "ANALYTICS_SYNC_INCOMPLETE" in expected and "SEO_ACTIVE_WEBSITE_MISSING" in expected
    unmapped = {code for code in expected if reason_of(code) is AutomationReason.UNMAPPED}
    assert not unmapped, f"add these to AutomationReason and FAILURE_POLICY: {sorted(unmapped)}"


def run(status: str, code: str | None = None) -> RunSnapshot:
    now = datetime(2026, 10, 1, tzinfo=UTC)
    return RunSnapshot(
        uuid4(), RunStatus(status), code, now, now, None if status in ("queued", "running") else now
    )


@pytest.mark.parametrize(
    ("code", "actions"),
    [
        ("GBP_PERFORMANCE_ACCESS_DENIED", ["reconnect_google_business_profile"]),
        ("ANALYTICS_SYNC_INCOMPLETE", ["check_analytics_connection"]),
        ("SEO_ACTIVE_WEBSITE_MISSING", ["connect_website"]),
    ],
)
def test_named_failures_need_attention_with_their_recovery_action(
    code: str, actions: list[str]
) -> None:
    for status in ("failed", "retry_scheduled"):
        latest = run(status, code)
        assert status_of("active", latest) is AutomationStatus.NEEDS_ATTENTION
        attention = attention_of(latest)
        assert attention is not None
        assert attention.reason.value == code
        assert [a.value for a in attention.actions] == actions


def test_rate_limit_will_retry_and_is_not_a_failure() -> None:
    for status in ("failed", "retry_scheduled"):
        latest = run(status, "GBP_PERFORMANCE_RATE_LIMITED")
        assert status_of("active", latest) is AutomationStatus.HEALTHY
        assert attention_of(latest) is None
        assert outcome_of(latest) is RunOutcome.WILL_RETRY


@pytest.mark.parametrize("code", ["VERIFICATION_CONTENT_PENDING", "VERIFICATION_REREAD_FAILED"])
def test_review_verification_codes_never_fail_an_automation(code: str) -> None:
    for status in ("failed", "retry_scheduled", "escalated"):
        latest = run(status, code)
        assert FAILURE_POLICY[AutomationReason(code)].treatment is Treatment.WILL_RETRY
        assert status_of("active", latest) is AutomationStatus.HEALTHY
        assert outcome_of(latest) is RunOutcome.WILL_RETRY


def test_unknown_code_gets_the_generic_fallback_and_is_still_attention() -> None:
    latest = run("failed", "SOMETHING_NEW")
    attention = attention_of(latest)
    assert attention is not None and attention.reason is AutomationReason.UNMAPPED
    assert attention.actions == ()
    assert status_of("active", run("failed")) is AutomationStatus.NEEDS_ATTENTION


def test_paused_never_run_running_and_recovered() -> None:
    failed = run("failed", "GBP_PERFORMANCE_ACCESS_DENIED")
    assert status_of("paused", failed) is AutomationStatus.PAUSED
    assert status_of("cancelled", None) is AutomationStatus.PAUSED
    assert status_of("active", None) is AutomationStatus.NOT_RUN_YET
    assert status_of("active", run("running")) is AutomationStatus.RUNNING
    assert status_of("active", run("completed")) is AutomationStatus.HEALTHY
    assert outcome_of(run("completed")) is RunOutcome.SUCCEEDED


def test_run_now_allowlist_is_read_only_and_never_publishes() -> None:
    assert {
        "gbp.sync",
        "gbp.sync_performance",
        "reviews.ingest",
        "seo.sync_search_console",
        "insights.sync_analytics",
        "seo.crawl_or_analysis",
    } == RUN_NOW_WORKFLOWS
    for key in known_workflow_keys():
        if "publish" in key or key.startswith(("content.", "agent.", "leads.")):
            assert key not in RUN_NOW_WORKFLOWS
    assert "gbp.generate_post" not in RUN_NOW_WORKFLOWS


def test_workflow_type_enum_matches_the_catalog() -> None:
    assert sorted(t.value for t in WorkflowTypeCode) == known_workflow_keys()


@pytest.mark.parametrize(
    ("cron", "kind", "fields"),
    [
        ("*/30 * * * *", FrequencyKind.INTERVAL_MINUTES, {"interval": 30}),
        ("0 * * * *", FrequencyKind.HOURLY, {"minute": 0}),
        ("0 */6 * * *", FrequencyKind.INTERVAL_HOURS, {"interval": 6, "minute": 0}),
        ("15 5 * * *", FrequencyKind.DAILY, {"hour": 5, "minute": 15}),
        ("0 7 * * 1", FrequencyKind.WEEKLY, {"hour": 7, "weekday": 1}),
        ("0 7 * * 7", FrequencyKind.WEEKLY, {"weekday": 0}),
        ("0 8 1 * *", FrequencyKind.MONTHLY, {"day_of_month": 1}),
        ("0 8 1 6 *", FrequencyKind.CUSTOM, {}),
        ("nonsense", FrequencyKind.CUSTOM, {}),
    ],
)
def test_frequency_is_a_typed_value(cron: str, kind: FrequencyKind, fields: dict[str, int]) -> None:
    value = parse_frequency(cron)
    assert value.kind is kind
    for name, expected in fields.items():
        assert getattr(value, name) == expected


def test_sources_by_workflow_type() -> None:
    assert source_of("gbp.sync_performance").value == "google_business_profile"
    assert source_of("reviews.ingest").value == "reviews"
    assert source_of("seo.crawl_or_analysis").value == "website"
    assert source_of("insights.sync_analytics").value == "analytics"
    assert source_of("seo.sync_search_console").value == "search_console"
