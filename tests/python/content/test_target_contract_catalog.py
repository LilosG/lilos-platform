"""The recorded client contracts must be usable by the mapping layer.

Each entry in the seed catalog was read from that repository's
src/content/config.ts. These tests check the catalog parses into a working
contract and that generated content satisfies it, so a typo in a field name or a
required field is caught here rather than by a failed client build.
"""

import pytest

from apps.api.app.products.content.frontmatter_contract import FrontmatterContract
from apps.api.app.products.content.service import build_publishable_frontmatter
from scripts.seed_publishing_target_contracts import CONTRACTS

GENERATED = build_publishable_frontmatter(
    title="Panel Upgrades in Carlsbad",
    ai_output={
        "meta_description": "When a 200-amp upgrade makes sense.",
        "faqs": [{"question": "How long does it take?", "answer": "Usually one day."}],
        "related_services": ["electrical-panel-upgrades"],
        "service_areas": ["carlsbad"],
        "category": "water-damage",
    },
    body="# Panel Upgrades\n\nBody copy.\n",
)


@pytest.mark.parametrize("repository_id", sorted(CONTRACTS))
def test_every_recorded_contract_parses(repository_id: str) -> None:
    contract = FrontmatterContract.from_document(CONTRACTS[repository_id])

    assert "title" in contract.required
    assert "description" in contract.required


@pytest.mark.parametrize("repository_id", sorted(CONTRACTS))
def test_generated_content_satisfies_every_recorded_contract(repository_id: str) -> None:
    """A page LILOs generates must build against each client's real schema."""
    contract = FrontmatterContract.from_document(CONTRACTS[repository_id])

    rendered = contract.render(GENERATED)

    assert contract.missing_required(rendered) == (), (
        f"{repository_id} would reject generated content: "
        f"missing {contract.missing_required(rendered)}"
    )


@pytest.mark.parametrize("repository_id", sorted(CONTRACTS))
def test_rendered_output_is_publishable(repository_id: str) -> None:
    from apps.api.app.products.content.file_format import build_content_file

    contract = FrontmatterContract.from_document(CONTRACTS[repository_id])
    output = build_content_file("Body copy.\n", contract.render(GENERATED))

    assert output.startswith("---\n")
    assert "\n---\n\n" in output


def test_date_field_names_differ_across_clients_as_recorded() -> None:
    """Guards the specific divergence that makes a shared contract unsafe."""
    date_keys = {
        repository_id: FrontmatterContract.from_document(document).target_key("publish_date")
        for repository_id, document in CONTRACTS.items()
    }

    assert date_keys["LilosG/wheylandelectric-final-2.0"] == "date"
    assert date_keys["LilosG/carlsbadfixit-final"] == "pubDate"
    assert date_keys["LilosG/tamarackrestoration-final-2.0"] == "publishDate"
    assert len(set(date_keys.values())) > 1


def test_contracts_never_use_canonical_names_as_target_keys_by_accident() -> None:
    """A mapping entry that renames a field to itself is a copy-paste slip."""
    for repository_id, document in CONTRACTS.items():
        for canonical, target in (document.get("field_names") or {}).items():
            assert canonical != target, f"{repository_id}: {canonical} maps to itself"
