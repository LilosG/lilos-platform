"""Focused tests for deterministic GBP proposal enrichment."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.app.config import Settings
from apps.api.app.integrations.google_drive_media import DriveImage
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
