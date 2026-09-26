"""Focused PostgreSQL contract for Packet 2 internal-link observations."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[3]
TABLE = "seo_internal_link_observations"


async def schema(postgresql_test_url: str) -> dict[str, Any]:
    engine = create_async_engine(postgresql_test_url)
    try:
        async with engine.connect() as connection:

            def read(sync_connection: Any) -> dict[str, Any]:
                inspector = inspect(sync_connection)
                if not inspector.has_table(TABLE):
                    indexes = sync_connection.execute(
                        text(
                            "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() "
                            "AND indexname IN (:source, :target)"
                        ),
                        {
                            "source": "ix_seo_internal_links_org_website_run_source",
                            "target": "ix_seo_internal_links_org_website_run_target",
                        },
                    ).all()
                    return {"table": False, "indexes": indexes}
                return {
                    "table": True,
                    "foreign_keys": inspector.get_foreign_keys(TABLE),
                    "uniques": inspector.get_unique_constraints(TABLE),
                    "checks": inspector.get_check_constraints(TABLE),
                    "indexes": inspector.get_indexes(TABLE),
                }

            return await connection.run_sync(read)
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_internal_link_migration_contract_and_reversibility(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.upgrade(config, "head")
    result = asyncio.run(schema(postgresql_test_url))
    assert result["table"] is True
    foreign_keys = {
        tuple(item["constrained_columns"]): (
            item["referred_table"],
            tuple(item["referred_columns"]),
        )
        for item in result["foreign_keys"]
    }
    assert foreign_keys[("organization_id", "website_id", "crawl_run_id")] == (
        "seo_crawl_runs",
        ("organization_id", "website_id", "id"),
    )
    assert foreign_keys[("organization_id", "website_id", "source_page_id")] == (
        "seo_pages",
        ("organization_id", "website_id", "id"),
    )
    assert foreign_keys[("organization_id", "website_id", "target_page_id")] == (
        "seo_pages",
        ("organization_id", "website_id", "id"),
    )
    assert any(
        item["name"] == "uq_seo_internal_link_run_source_fingerprint"
        and item["column_names"] == ["crawl_run_id", "source_page_id", "link_fingerprint"]
        for item in result["uniques"]
    )
    checks = {item["name"] for item in result["checks"]}
    assert "ck_seo_internal_link_observations_positive_occurrence_count" in checks
    assert "ck_seo_internal_link_observations_target_mapping_consistent" in checks
    indexes = {item["name"]: item for item in result["indexes"]}
    for name, columns in (
        (
            "ix_seo_internal_links_org_website_run_source",
            ["organization_id", "website_id", "crawl_run_id", "source_page_id"],
        ),
        (
            "ix_seo_internal_links_org_website_run_target",
            ["organization_id", "website_id", "crawl_run_id", "target_page_id"],
        ),
    ):
        assert indexes[name]["column_names"] == columns
        assert indexes[name]["unique"] is False
    command.check(config)
    command.downgrade(config, "20260925_0001")
    removed = asyncio.run(schema(postgresql_test_url))
    assert removed == {"table": False, "indexes": []}
    command.upgrade(config, "head")
    restored = asyncio.run(schema(postgresql_test_url))
    assert restored["table"] is True
    assert {item["name"] for item in restored["indexes"]} == set(indexes)
    command.check(config)
