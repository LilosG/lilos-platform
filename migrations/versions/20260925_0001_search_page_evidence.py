"""Pin provider page evidence to organization and website scope."""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260925_0001"
down_revision: str | Sequence[str] | None = "20260924_0001"
branch_labels = depends_on = None
MARKER = "lilos:20260925_0001"


def _column(table: str, name: str, type_: sa.types.TypeEngine[Any]) -> None:
    if any(item["name"] == name for item in sa.inspect(op.get_bind()).get_columns(table)):
        return
    op.add_column(table, sa.Column(name, type_, nullable=True))
    op.execute(sa.text(f"COMMENT ON COLUMN {table}.{name} IS '{MARKER}'"))


def _comment(table: str, name: str) -> str | None:
    return (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT obj_description(c.oid, 'pg_constraint') FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname = :table AND c.conname = :name "
                "AND t.relnamespace = "
                "(SELECT oid FROM pg_namespace WHERE nspname = current_schema())"
            ),
            {"table": table, "name": name},
        )
        .scalar_one_or_none()
    )


def _foreign_key(table: str, target: str, columns: list[str], remote: list[str]) -> None:
    name = f"fk_{table}_organization_id_{target}"
    existing = next(
        (
            item
            for item in sa.inspect(op.get_bind()).get_foreign_keys(table)
            if item["name"] == name
        ),
        None,
    )
    if existing is not None:
        if (
            existing["constrained_columns"] == columns
            and existing["referred_table"] == target
            and existing["referred_columns"] == remote
        ):
            return
        if not (
            table == "seo_search_observations"
            and target == "seo_pages"
            and existing["constrained_columns"] == ["organization_id", "page_id"]
            and existing["referred_columns"] == ["organization_id", "id"]
        ):
            raise RuntimeError(f"Unexpected foreign key contract for {name}")
        op.drop_constraint(name, table, type_="foreignkey")
    op.create_foreign_key(name, table, target, columns, remote, ondelete="RESTRICT")
    op.execute(sa.text(f"COMMENT ON CONSTRAINT {name} ON {table} IS '{MARKER}'"))


def _check(table: str) -> None:
    name = f"ck_{table}_page_requires_website"
    if any(item["name"] == name for item in sa.inspect(op.get_bind()).get_check_constraints(table)):
        return
    expression = (
        "page_id IS NULL OR website_id IS NOT NULL OR resolver_version IS NULL"
        if table == "seo_search_observations"
        else "page_id IS NULL OR website_id IS NOT NULL"
    )
    op.create_check_constraint(name, table, expression)
    op.execute(sa.text(f"COMMENT ON CONSTRAINT {name} ON {table} IS '{MARKER}'"))


def _drop_created_column(table: str, name: str) -> None:
    marker = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT col_description(t.oid, a.attnum) FROM pg_class t "
                "JOIN pg_attribute a ON a.attrelid = t.oid "
                "WHERE t.relname = :table AND a.attname = :name "
                "AND t.relnamespace = "
                "(SELECT oid FROM pg_namespace WHERE nspname = current_schema())"
            ),
            {"table": table, "name": name},
        )
        .scalar_one_or_none()
    )
    if marker == MARKER:
        op.drop_column(table, name)


def _ensure_index(table: str, name: str, columns: list[str]) -> None:
    existing = next(
        (item for item in sa.inspect(op.get_bind()).get_indexes(table) if item["name"] == name),
        None,
    )
    if existing is not None:
        if existing["column_names"] != columns or existing["unique"]:
            raise RuntimeError(f"Unexpected index contract for {name}")
        return
    op.create_index(name, table, columns)
    op.execute(sa.text(f"COMMENT ON INDEX {name} IS '{MARKER}'"))


def _index_comment(table: str, name: str) -> str | None:
    return (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT obj_description(i.oid, 'pg_class') FROM pg_class i "
                "JOIN pg_namespace n ON n.oid = i.relnamespace "
                "JOIN pg_index x ON x.indexrelid = i.oid "
                "JOIN pg_class t ON t.oid = x.indrelid "
                "WHERE n.nspname = current_schema() AND i.relname = :name "
                "AND t.relname = :table"
            ),
            {"table": table, "name": name},
        )
        .scalar_one_or_none()
    )


def upgrade() -> None:
    for name, search_type in (
        ("website_id", postgresql.UUID(as_uuid=True)),
        ("mapping_state", sa.String(16)),
        ("mapping_basis", sa.String(32)),
        ("resolver_version", sa.String(32)),
        ("mapping_limitation", sa.Text()),
    ):
        _column("seo_search_observations", name, search_type)
    for name in ("website_id", "page_id"):
        _column("metric_observations", name, postgresql.UUID(as_uuid=True))
    for name, analytics_type in (
        ("page_evidence_status", sa.String(16)),
        ("page_evidence_limitation", sa.String(500)),
        ("page_evidence_checked_at", sa.DateTime(timezone=True)),
    ):
        _column("analytics_properties", name, analytics_type)
    for table in ("seo_search_observations", "metric_observations"):
        _foreign_key(
            table, "seo_websites", ["organization_id", "website_id"], ["organization_id", "id"]
        )
        _foreign_key(
            table,
            "seo_pages",
            ["organization_id", "website_id", "page_id"],
            ["organization_id", "website_id", "id"],
        )
        _check(table)
    _ensure_index(
        "seo_search_observations",
        "ix_seo_search_observations_org_website_page_date_end",
        ["organization_id", "website_id", "page_id", "date_end"],
    )
    _ensure_index(
        "metric_observations",
        "ix_metric_observations_org_website_page_period_end",
        ["organization_id", "website_id", "page_id", "period_end"],
    )


def downgrade() -> None:
    for table, name in (
        ("metric_observations", "ix_metric_observations_org_website_page_period_end"),
        ("seo_search_observations", "ix_seo_search_observations_org_website_page_date_end"),
    ):
        if _index_comment(table, name) == MARKER:
            op.drop_index(name, table_name=table)
    for table in ("metric_observations", "seo_search_observations"):
        check = f"ck_{table}_page_requires_website"
        if _comment(table, check) == MARKER:
            op.drop_constraint(check, table, type_="check")
        page_fk = f"fk_{table}_organization_id_seo_pages"
        if _comment(table, page_fk) == MARKER:
            op.drop_constraint(page_fk, table, type_="foreignkey")
            if table == "seo_search_observations":
                op.create_foreign_key(
                    page_fk,
                    table,
                    "seo_pages",
                    ["organization_id", "page_id"],
                    ["organization_id", "id"],
                    ondelete="RESTRICT",
                )
        website_fk = f"fk_{table}_organization_id_seo_websites"
        if _comment(table, website_fk) == MARKER:
            op.drop_constraint(website_fk, table, type_="foreignkey")
    for name in ("page_evidence_checked_at", "page_evidence_limitation", "page_evidence_status"):
        _drop_created_column("analytics_properties", name)
    for name in ("page_id", "website_id"):
        _drop_created_column("metric_observations", name)
    for name in (
        "mapping_limitation",
        "resolver_version",
        "mapping_basis",
        "mapping_state",
        "website_id",
    ):
        _drop_created_column("seo_search_observations", name)
