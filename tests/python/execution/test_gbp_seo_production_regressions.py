"""Regression contracts for production failures observed on 2026-09-03."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from apps.api.app.ai.providers import (
    OpenRouterProvider,
    _build_prompt,
    _looks_like_review_response,
)
from apps.api.app.execution import operational_extensions
from apps.api.app.execution.contracts import JobOutcome


class FakeResponse:
    status_code = 200

    def json(self) -> dict[str, Any]:
        return {
            "id": "gbp-production-regression",
            "model": "deepseek/deepseek-v4-flash-0731",
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "draft": (
                                    "Thank you for the 5-star review! We're so glad you enjoyed "
                                    "your visit and hope to welcome you back soon."
                                )
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 30,
                "total_tokens": 130,
                "cost": 0.0001,
            },
        }


class FakeClient:
    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        del url, kwargs
        return FakeResponse()


@pytest.mark.anyio
async def test_gbp_local_post_rejects_review_response_voice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback = (
        'A recent customer shared: "A great weekend experience." '
        "Coco Maya appreciates the feedback and the opportunity to help. "
        "Learn more about the experience."
    )
    monkeypatch.setattr(
        "apps.api.app.ai.providers.httpx.AsyncClient",
        lambda *args, **kwargs: FakeClient(),
    )

    output = await OpenRouterProvider(
        api_key="test-key",
        default_model="deepseek/deepseek-v4-flash-0731",
    ).generate(
        task_key="gbp.generate_post",
        input_document={
            "audience": "local prospective customers",
            "intent": "create one Google Business Profile update based on the selected review",
            "content_title": "Customer review about brunch",
            "content_type": "gbp_post",
            "source_type": "google_review",
            "source_review": {
                "rating": 5,
                "body": "We had a great bachelorette weekend.",
            },
            "governed_facts": [
                {
                    "fact_key": "business.name",
                    "value": "Coco Maya",
                    "authority": "client",
                }
            ],
            "manual_fallback": fallback,
            "selected_target_url": "https://example.com/brunch/",
        },
        maximum_tokens=500,
    )

    assert _looks_like_review_response(
        "Thank you for the 5-star review! We're so glad you enjoyed your visit."
    )
    assert output["draft"] == fallback
    assert not _looks_like_review_response(str(output["draft"]))


def test_gbp_generation_has_a_dedicated_local_post_prompt() -> None:
    prompt = _build_prompt(
        "gbp.generate_post",
        {
            "audience": "local prospective customers",
            "intent": "create a GBP update",
            "source_type": "google_review",
            "source_review": {"rating": 5, "body": "Great experience"},
            "governed_facts": [],
        },
    )

    assert "Google Business Profile Local Post" in prompt
    assert "NOT a response to a customer review" in prompt
    assert "Never address the reviewer directly" in prompt
    assert "Task: gbp.generate_post" not in prompt


class FakeSession:
    def __init__(self, scalar_results: list[object]) -> None:
        self._scalar_results = list(scalar_results)
        self.flushed = False

    async def scalar(self, statement: object) -> object | None:
        del statement
        return self._scalar_results.pop(0) if self._scalar_results else None

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.anyio
async def test_combined_seo_workflow_activates_successfully_crawled_pending_website(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid4()
    location_id = uuid4()
    crawl_run_id = uuid4()
    website_id = uuid4()
    crawl_run = SimpleNamespace(
        id=crawl_run_id,
        website_id=website_id,
        status="success",
        safe_result={"pages_crawled": 12},
    )
    website = SimpleNamespace(
        id=website_id,
        location_id=location_id,
        status="pending_verification",
        ownership_status="unverified",
        verified_at=None,
        version=1,
    )
    session = FakeSession([crawl_run, website])

    async def successful_crawl(*args: object, **kwargs: object) -> JobOutcome:
        del args, kwargs
        return JobOutcome(result="succeeded", result_reference=f"crawl_run:{crawl_run_id}")

    class FakeOrchestration:
        called = False

        async def analyze(self, *args: object, **kwargs: object) -> dict[str, object]:
            del args, kwargs
            self.called = True
            return {
                "status": "completed",
                "website_id": str(website_id),
                "seo_opportunities": 2,
            }

    orchestration = FakeOrchestration()
    monkeypatch.setattr(operational_extensions, "_handle_seo_crawl", successful_crawl)
    monkeypatch.setattr(
        operational_extensions,
        "SEOOrchestrationService",
        lambda: orchestration,
    )

    outcome = await operational_extensions._handle_seo_crawl_and_analysis(
        session,  # type: ignore[arg-type]
        organization_id=organization_id,
        location_id=location_id,
        input_document={"crawl_run_id": str(crawl_run_id)},
        correlation_id="seo-production-regression",
        workflow_run_id=uuid4(),
    )

    assert outcome.result == "succeeded"
    assert website.status == "active"
    assert website.ownership_status == "unverified"
    assert website.verified_at is None
    assert website.version == 2
    assert session.flushed is True
    assert orchestration.called is True


@pytest.mark.anyio
async def test_combined_seo_workflow_does_not_analyze_errored_crawl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid4()
    crawl_run_id = uuid4()
    crawl_run = SimpleNamespace(
        id=crawl_run_id,
        website_id=uuid4(),
        status="error",
        safe_result={"pages_crawled": 0},
    )
    session = FakeSession([crawl_run])

    async def reported_success(*args: object, **kwargs: object) -> JobOutcome:
        del args, kwargs
        return JobOutcome(result="succeeded", result_reference=f"crawl_run:{crawl_run_id}")

    class MustNotAnalyze:
        async def analyze(self, *args: object, **kwargs: object) -> dict[str, object]:
            del args, kwargs
            raise AssertionError("analysis must not run after an errored crawl")

    monkeypatch.setattr(operational_extensions, "_handle_seo_crawl", reported_success)
    monkeypatch.setattr(operational_extensions, "SEOOrchestrationService", MustNotAnalyze)

    outcome = await operational_extensions._handle_seo_crawl_and_analysis(
        session,  # type: ignore[arg-type]
        organization_id=organization_id,
        location_id=None,
        input_document={"crawl_run_id": str(crawl_run_id)},
        correlation_id="seo-error-regression",
        workflow_run_id=uuid4(),
    )

    assert outcome.result == "retryable_failure"
    assert outcome.safe_error == "SEO_CRAWL_FAILED"
