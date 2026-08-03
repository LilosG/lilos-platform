from uuid import uuid4

import pytest

from apps.api.app.products.content.adapter import validate_target_path
from apps.api.app.products.content.models import ContentPublication, ContentRevision
from apps.api.app.products.content.service import validate_content


def test_target_path_is_allowlisted_and_traversal_safe() -> None:
    assert (
        validate_target_path("src/content/blog/example.md", "src/content")
        == "src/content/blog/example.md"
    )
    for path in (
        "../secret.md",
        "/etc/passwd",
        ".github/workflows/deploy.yml",
        "src/content/unsafe.py",
    ):
        with pytest.raises(ValueError):
            validate_target_path(path, "src/content")


def test_content_validation_requires_grounding_and_rejects_secrets_and_code() -> None:
    result = validate_content("<script>alert(1)</script> api_key=bad", {"title": "Test"}, [], [])
    assert {"approved_fact_grounding_missing", "secret_like_content", "executable_content"} <= set(
        result["errors"]
    )


def test_prohibited_claim_is_not_publishable() -> None:
    result = validate_content("We are the guaranteed best.", {}, ["guaranteed best"], [uuid4()])
    assert result["valid"] is False


def test_publication_state_distinguishes_pr_build_deploy_and_verify() -> None:
    assert {
        "external_pull_request_id",
        "build_status",
        "deployment_status",
        "verified_at",
        "rollback_of_publication_id",
    } <= set(ContentPublication.__table__.columns.keys())
    assert {"content_hash", "approved_fact_revision_ids", "status", "validation_document"} <= set(
        ContentRevision.__table__.columns.keys()
    )
