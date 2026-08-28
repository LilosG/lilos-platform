"""Focused tests for deterministic GBP proposal enrichment."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.app.config import Settings
from apps.api.app.integrations.google_drive_media import (
    DriveDiscovery,
    DriveDiscoveryError,
    DriveImage,
)
from apps.api.app.products.gbp.proposal_enrichment import (
    GBPPostProposalEnrichmentService,
    GBPProposalEnrichmentError,
)


def _image(name: str, path: str, modified: str = "2026-08-25T12:00:00Z") -> DriveImage:
    return DriveImage(
        file_id=f"id-{name}",
        name=name,
        mime_type="image/jpeg",
        path=path,
        modified_time=modified,
    )


def test_select_image_prefers_work_folder_and_topic_match() -> None:
    images = [
        _image("panel-upgrade.jpg", "Wheyland Electric/work/panel-upgrade.jpg"),
        _image("truck.jpg", "Wheyland Electric/general/truck.jpg"),
        _image("holiday-lights.jpg", "Wheyland Electric/seasonal/holiday-lights.jpg"),
    ]

    selected = GBPPostProposalEnrichmentService._select_image(
        images,
        "Need an electrical panel upgrade before adding an EV charger?",
    )

    assert selected is not None
    assert selected.name == "panel-upgrade.jpg"


def test_select_image_prefers_seasonal_folder_for_seasonal_post() -> None:
    images = [
        _image("service-call.jpg", "Wheyland Electric/work/service-call.jpg"),
        _image("holiday-lights.jpg", "Wheyland Electric/seasonal/holiday-lights.jpg"),
    ]

    selected = GBPPostProposalEnrichmentService._select_image(
        images,
        "Holiday lighting and winter electrical safety tips for homeowners.",
    )

    assert selected is not None
    assert selected.name == "holiday-lights.jpg"


def test_select_image_falls_back_to_general_when_work_folder_missing() -> None:
    images = [
        _image("truck.jpg", "Wheyland Electric/general/truck.jpg"),
        _image("holiday-lights.jpg", "Wheyland Electric/seasonal/holiday-lights.jpg"),
    ]

    selected = GBPPostProposalEnrichmentService._select_image(
        images,
        "Electrical safety inspections for North County homeowners.",
    )

    assert selected is not None
    assert selected.name == "truck.jpg"


def test_target_url_prefers_relevant_service_page() -> None:
    profile: dict[str, object] = {"websiteUri": "https://wheylandelectric.com/"}
    knowledge = {
        "website_knowledge": [
            {
                "url": "https://wheylandelectric.com/",
                "title": "Wheyland Electric",
                "h1": "Electrician in North County San Diego",
                "body_text": "Residential electrical services.",
            },
            {
                "url": "https://wheylandelectric.com/services/ev-charger-installation/",
                "title": "EV Charger Installation",
                "h1": "Home EV Charger Installation",
                "body_text": "Level 2 charger installation and electrical panel evaluation.",
            },
        ]
    }

    target = GBPPostProposalEnrichmentService._select_target_url(
        profile,
        knowledge,
        "Planning to install a Level 2 EV charger at home?",
    )

    assert target == "https://wheylandelectric.com/services/ev-charger-installation/"


def test_target_url_does_not_fall_back_to_homepage_without_relevance() -> None:
    profile: dict[str, object] = {"websiteUri": "https://wheylandelectric.com/"}
    knowledge = {
        "website_knowledge": [
            {
                "url": "https://wheylandelectric.com/services/panel-upgrades/",
                "title": "Electrical Panel Upgrades",
                "h1": "Panel Upgrades",
                "body_text": "Upgrade residential electrical panels.",
            }
        ]
    }

    target = GBPPostProposalEnrichmentService._select_target_url(
        profile,
        knowledge,
        "A customer praised the team for installing recessed kitchen lighting.",
    )

    assert target is None


def test_cta_rejects_external_model_url_and_uses_client_target() -> None:
    target = "https://wheylandelectric.com/services/ev-charger-installation/"

    cta = GBPPostProposalEnrichmentService._safe_call_to_action(
        {"actionType": "LEARN_MORE", "url": "https://example.net/redirect"},
        target,
    )

    assert cta == {"actionType": "LEARN_MORE", "url": target}


@pytest.mark.anyio
async def test_drive_media_is_required_for_automated_proposals() -> None:
    service = GBPPostProposalEnrichmentService()
    session = AsyncMock()
    session.scalar.return_value = None
    settings = Settings(google_drive_service_account_json=None)

    with pytest.raises(GBPProposalEnrichmentError) as exc_info:
        await service._attach_best_drive_image(
            session,
            settings,
            organization_id=uuid4(),
            organization_name="Wheyland Electric",
            post_revision_id=uuid4(),
            content="Electrical panel upgrade in Carlsbad.",
        )

    assert exc_info.value.safe_code == "GBP_DRIVE_MEDIA_NOT_CONFIGURED"


@pytest.mark.anyio
async def test_classified_drive_failure_reaches_the_operator_unchanged() -> None:
    """The Wheyland run reported GBP_DRIVE_MEDIA_UNAVAILABLE and nothing else.

    Every Drive fault — malformed credential, rejected key, Drive API not enabled,
    folder never shared — arrived as that one code with one generic sentence, so
    the operator could not tell which of four unrelated fixes applied. The Drive
    layer classifies the cause now, and this proves the classification survives
    the enrichment boundary instead of being collapsed again.
    """
    service = GBPPostProposalEnrichmentService()
    session = AsyncMock()
    session.scalar.return_value = None
    settings = Settings(google_drive_service_account_json='{"client_email": "a@b.com"}')

    service.drive = AsyncMock()
    service.drive.discover.side_effect = DriveDiscoveryError(
        "GBP_DRIVE_ACCESS_DENIED",
        "Google Drive denied the service account (403: accessNotConfigured).",
        retryable=False,
    )

    with pytest.raises(GBPProposalEnrichmentError) as exc_info:
        await service._attach_best_drive_image(
            session,
            settings,
            organization_id=uuid4(),
            organization_name="Wheyland Electric",
            post_revision_id=uuid4(),
            content="HOA property maintenance electrical work in Carlsbad.",
        )

    assert exc_info.value.safe_code == "GBP_DRIVE_ACCESS_DENIED"
    assert "accessNotConfigured" in str(exc_info.value)


@pytest.mark.anyio
async def test_unclassified_drive_failure_still_fails_closed() -> None:
    """An unexpected error must not become a post without media."""
    service = GBPPostProposalEnrichmentService()
    session = AsyncMock()
    session.scalar.return_value = None
    settings = Settings(google_drive_service_account_json='{"client_email": "a@b.com"}')

    service.drive = AsyncMock()
    service.drive.discover.side_effect = RuntimeError("unexpected")

    with pytest.raises(GBPProposalEnrichmentError) as exc_info:
        await service._attach_best_drive_image(
            session,
            settings,
            organization_id=uuid4(),
            organization_name="Wheyland Electric",
            post_revision_id=uuid4(),
            content="HOA property maintenance electrical work in Carlsbad.",
        )

    assert exc_info.value.safe_code == "GBP_DRIVE_MEDIA_UNAVAILABLE"


@pytest.mark.anyio
async def test_no_eligible_image_says_nothing_is_shared_when_drive_is_empty() -> None:
    """Three situations shared one message; this is the first of them.

    A run reported GBP_DRIVE_NO_ELIGIBLE_IMAGE with nothing else, and the operator
    could not tell whether the folder was unshared, held no images, or was simply
    named something the tenant match does not recognise.
    """
    service = GBPPostProposalEnrichmentService()
    session = AsyncMock()
    session.scalar.return_value = None
    settings = Settings(google_drive_service_account_json='{"client_email": "a@b.com"}')

    service.drive = AsyncMock()
    service.drive.discover.return_value = DriveDiscovery(
        images=[],
        visible_files=0,
        visible_images=0,
        service_account_email="drive@lilos-prod.iam.gserviceaccount.com",
        match_terms=("electric", "wheyland"),
    )

    with pytest.raises(GBPProposalEnrichmentError) as exc_info:
        await service._attach_best_drive_image(
            session,
            settings,
            organization_id=uuid4(),
            organization_name="Wheyland Electric",
            post_revision_id=uuid4(),
            content="HOA common-area lighting maintenance.",
        )

    message = str(exc_info.value)
    assert exc_info.value.safe_code == "GBP_DRIVE_NO_ELIGIBLE_IMAGE"
    assert "can see no files at all" in message
    # The address to share the folder with, so the fix needs no hunting.
    assert "drive@lilos-prod.iam.gserviceaccount.com" in message


@pytest.mark.anyio
async def test_no_eligible_image_says_the_folder_does_not_name_the_client() -> None:
    service = GBPPostProposalEnrichmentService()
    session = AsyncMock()
    session.scalar.return_value = None
    settings = Settings(google_drive_service_account_json='{"client_email": "a@b.com"}')

    service.drive = AsyncMock()
    service.drive.discover.return_value = DriveDiscovery(
        images=[],
        visible_files=412,
        visible_images=96,
        service_account_email="drive@lilos-prod.iam.gserviceaccount.com",
        match_terms=("electric", "wheyland"),
    )

    with pytest.raises(GBPProposalEnrichmentError) as exc_info:
        await service._attach_best_drive_image(
            session,
            settings,
            organization_id=uuid4(),
            organization_name="Wheyland Electric",
            post_revision_id=uuid4(),
            content="HOA common-area lighting maintenance.",
        )

    message = str(exc_info.value)
    assert "412" in message and "96" in message
    assert "wheyland" in message and "electric" in message


@pytest.mark.anyio
async def test_no_eligible_image_says_the_shared_folder_holds_no_images() -> None:
    service = GBPPostProposalEnrichmentService()
    session = AsyncMock()
    session.scalar.return_value = None
    settings = Settings(google_drive_service_account_json='{"client_email": "a@b.com"}')

    service.drive = AsyncMock()
    service.drive.discover.return_value = DriveDiscovery(
        images=[],
        visible_files=38,
        visible_images=0,
        service_account_email="drive@lilos-prod.iam.gserviceaccount.com",
        match_terms=("electric", "wheyland"),
    )

    with pytest.raises(GBPProposalEnrichmentError) as exc_info:
        await service._attach_best_drive_image(
            session,
            settings,
            organization_id=uuid4(),
            organization_name="Wheyland Electric",
            post_revision_id=uuid4(),
            content="HOA common-area lighting maintenance.",
        )

    assert "no images among them" in str(exc_info.value)


def test_the_explanation_never_names_another_clients_folders() -> None:
    """This text reaches an agent run scoped to one organization.

    Listing the folder names the service account can see would put other clients'
    business names into this client's run context — a cross-tenant leak.
    """
    discovery = DriveDiscovery(
        images=[],
        visible_files=412,
        visible_images=96,
        service_account_email="drive@lilos-prod.iam.gserviceaccount.com",
        match_terms=("electric", "wheyland"),
    )

    explanation = discovery.explain()
    for other_client in ("Blue Door Pest", "Tamarack", "Carlsbad Fix It"):
        assert other_client.lower() not in explanation.lower()
