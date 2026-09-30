"""The GA4 website backfill migration must bind only unambiguous mappings."""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[3]


async def _seed(database_url: str) -> dict[str, object]:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            single_org = uuid4()
            multi_org = uuid4()
            empty_org = uuid4()
            already_mapped_org = uuid4()
            single_website = uuid4()
            multi_website_a = uuid4()
            multi_website_b = uuid4()
            single_property = uuid4()
            multi_property = uuid4()
            empty_property = uuid4()
            already_mapped_property = uuid4()
            already_mapped_website = uuid4()

            for org_id, name in (
                (single_org, "single"),
                (multi_org, "multi"),
                (empty_org, "empty"),
                (already_mapped_org, "already-mapped"),
            ):
                await connection.execute(
                    text(
                        "INSERT INTO organizations (id, name, slug, organization_type, "
                        "status, timezone, default_currency, version, created_at, updated_at) "
                        "VALUES (:id, :name, :slug, 'test', 'active', 'UTC', 'USD', 1, "
                        "now(), now())"
                    ),
                    {"id": org_id, "name": name, "slug": f"backfill-{name}-{uuid4().hex[:8]}"},
                )

            for website_id, org_id, key in (
                (single_website, single_org, "single"),
                (multi_website_a, multi_org, "multi-a"),
                (multi_website_b, multi_org, "multi-b"),
                (already_mapped_website, already_mapped_org, "already-mapped"),
            ):
                await connection.execute(
                    text(
                        "INSERT INTO seo_websites (id, organization_id, key, name, "
                        "canonical_origin, status, ownership_status, version, "
                        "created_at, updated_at) VALUES (:id, :org, :key, :key, "
                        "'https://example.invalid', 'active', 'verified', 1, now(), now())"
                    ),
                    {"id": website_id, "org": org_id, "key": key},
                )

            provider_id = uuid4()
            await connection.execute(
                text(
                    "INSERT INTO integration_providers (id, key, name, status, capabilities, "
                    "manifest_version, created_at, updated_at) VALUES "
                    "(:id, :key, 'Google', 'active', '[]'::jsonb, 1, now(), now())"
                ),
                {"id": provider_id, "key": f"google-{uuid4().hex[:8]}"},
            )
            connection_by_org: dict[object, object] = {}
            for org_id in (single_org, multi_org, empty_org, already_mapped_org):
                connection_id = uuid4()
                await connection.execute(
                    text(
                        "INSERT INTO integration_connections (id, organization_id, "
                        "provider_id, external_account_reference, status, version, "
                        "created_at, updated_at) VALUES (:id, :org, :provider, "
                        "'backfill-test', 'connected', 1, now(), now())"
                    ),
                    {"id": connection_id, "org": org_id, "provider": provider_id},
                )
                connection_by_org[org_id] = connection_id

            property_rows: tuple[tuple[object, object, object, str], ...] = (
                (single_property, single_org, None, "properties/single"),
                (multi_property, multi_org, None, "properties/multi"),
                (empty_property, empty_org, None, "properties/empty"),
                (
                    already_mapped_property,
                    already_mapped_org,
                    already_mapped_website,
                    "properties/mapped",
                ),
            )
            for prop_id, prop_org_id, prop_website_id, external_id in property_rows:
                await connection.execute(
                    text(
                        "INSERT INTO analytics_properties (id, organization_id, connection_id, "
                        "website_id, provider, external_property_id, property_number, "
                        "display_name, mapping_status, freshness_status, created_at, updated_at) "
                        "VALUES (:id, :org, :connection, :website, 'google_analytics', "
                        ":external_id, '1', 'Test property', 'mapped', 'never_synced', "
                        "now(), now())"
                    ),
                    {
                        "id": prop_id,
                        "org": prop_org_id,
                        "connection": connection_by_org[prop_org_id],
                        "website": prop_website_id,
                        "external_id": external_id,
                    },
                )

        return {
            "single_property": single_property,
            "single_website": single_website,
            "multi_property": multi_property,
            "empty_property": empty_property,
            "already_mapped_property": already_mapped_property,
            "already_mapped_website": already_mapped_website,
        }
    finally:
        await engine.dispose()


async def _read_website_ids(database_url: str, property_ids: list[object]) -> dict[object, object]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text("SELECT id, website_id FROM analytics_properties WHERE id = ANY(:ids)"),
                {"ids": property_ids},
            )
            return {row.id: row.website_id for row in rows}
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_backfill_binds_only_organizations_with_exactly_one_website(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    # Reset to a known state first: this session's database may already be at
    # a later revision (or hold data) from another migration test that ran
    # earlier against the same shared postgresql_test_url.
    command.downgrade(config, "base")
    command.upgrade(config, "20260929_0002")

    seeded = asyncio.run(_seed(postgresql_test_url))
    command.upgrade(config, "head")
    website_by_property = asyncio.run(
        _read_website_ids(
            postgresql_test_url,
            [
                seeded["single_property"],
                seeded["multi_property"],
                seeded["empty_property"],
                seeded["already_mapped_property"],
            ],
        )
    )

    # Exactly one website in its organization -> bound.
    assert website_by_property[seeded["single_property"]] == seeded["single_website"]
    # Two websites in its organization -> left NULL, not guessed.
    assert website_by_property[seeded["multi_property"]] is None
    # No websites in its organization -> left NULL.
    assert website_by_property[seeded["empty_property"]] is None
    # Already had a website_id -> untouched by the backfill.
    assert (
        website_by_property[seeded["already_mapped_property"]] == (seeded["already_mapped_website"])
    )
