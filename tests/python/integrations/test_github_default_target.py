"""Small invariant test for the managed Astro publishing convention."""

from apps.api.app.products.content.github_app_service import DiscoveredRepository
from apps.api.app.products.content.publishing_target_reconciliation import (
    select_repository_for_client,
)


def test_managed_astro_blog_path_convention() -> None:
    # Single-repository GitHub App installations are reconciled to this
    # repository-relative path by the integration callback/workspace.
    assert "src/content/blog".startswith("src/content/")


def _repo(name: str, *, homepage: str | None = None) -> DiscoveredRepository:
    return DiscoveredRepository(
        repository_id=f"LilosG/{name}",
        name=name,
        default_branch="main",
        private=True,
        homepage=homepage,
    )


def test_repository_selection_uses_exact_client_homepage_when_installation_has_many_repos() -> None:
    selected = select_repository_for_client(
        [
            _repo("other-client", homepage="https://other.example"),
            _repo("louisiana-purchase", homepage="https://louisianapurchasesd.com"),
        ],
        primary_domain="louisianapurchasesd.com",
        website_url="https://louisianapurchasesd.com/",
        organization_slug="louisiana-purchase",
    )

    assert selected is not None
    assert selected.repository_id == "LilosG/louisiana-purchase"


def test_repository_selection_uses_unique_normalized_client_name_without_homepage() -> None:
    selected = select_repository_for_client(
        [_repo("park-101"), _repo("Louisiana-Purchase")],
        primary_domain="louisianapurchase.com",
        website_url=None,
        organization_slug="louisiana-purchase",
    )

    assert selected is not None
    assert selected.repository_id == "LilosG/Louisiana-Purchase"


def test_repository_selection_refuses_ambiguous_client_mapping() -> None:
    selected = select_repository_for_client(
        [_repo("client-site"), _repo("client_site")],
        primary_domain="clientsite.com",
        website_url=None,
        organization_slug="client-site",
    )

    assert selected is None
