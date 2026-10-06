"""The database, not the application, decides who may delete governed history.

Eighteen tables refuse every DELETE by trigger. A removal must be able to delete an
organization's rows, so each trigger function now allows a DELETE only when the row's
organization is archived, has a removal requested and is not yet removed
(``lilos_organization_removal_in_progress`` reads that from ``organizations`` itself). These
tests prove, table by table, that the delete is refused for every other organization and every
other state, and allowed only for the organization being removed.

Real governed rows need dozens of parents and check constraints, so each table is exercised
through a shadow copy: ``CREATE TEMP TABLE ... (LIKE real)`` with the table's own delete
trigger definition re-created on it, which runs the exact trigger function the real table uses.
"""

import re
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.database.base import utc_now
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization

GOVERNED_TABLES = (
    "business_fact_revisions",
    "configuration_definitions",
    "configuration_revisions",
    "content_revisions",
    "feature_flag_revisions",
    "gbp_post_revisions",
    "offboarding_plans",
    "offboarding_steps",
    "onboarding_checklist_items",
    "policy_revisions",
    "product_entitlement_locations",
    "product_entitlements",
    "products",
    "report_revisions",
    "runtime_control_revisions",
    "seo_recommendation_revisions",
    "service_assignments",
    "service_catalog",
)
# Catalogs with no organization at all: nothing may ever delete them.
GLOBAL_TABLES = frozenset({"configuration_definitions", "products"})
GUARDED_FUNCTIONS = frozenset(
    {
        "prevent_content_revision_change",
        "prevent_seo_recommendation_change",
        "prevent_gbp_post_revision_change",
        "prevent_report_revision_change",
        "prevent_phase4_governed_delete",
    }
)


async def make_organization(
    session: AsyncSession,
    label: str,
    *,
    status: OrganizationStatus,
    requested: bool = False,
    removed: bool = False,
) -> UUID:
    now = utc_now()
    organization = Organization(
        name=label,
        slug=f"{label}-{uuid4().hex[:6]}",
        organization_type=OrganizationType.TEST,
        status=status,
        timezone="UTC",
        default_currency="USD",
        archived_at=now if status is OrganizationStatus.ARCHIVED else None,
        removal_requested_at=now if requested else None,
        removed_at=now if removed else None,
        version=1,
    )
    session.add(organization)
    await session.flush()
    return organization.id


async def shadow_of(session: AsyncSession, table: str) -> tuple[str, set[str]]:
    """A temp copy of ``table`` carrying the table's own DELETE trigger(s)."""
    shadow = f"shadow_{table}"
    await session.execute(
        text(f"CREATE TEMP TABLE {shadow} (LIKE public.{table} INCLUDING DEFAULTS)")
    )
    required = await session.execute(
        text(
            "SELECT attname FROM pg_attribute WHERE attrelid = CAST(:shadow AS regclass) "
            "AND attnum > 0 AND NOT attisdropped AND attnotnull"
        ),
        {"shadow": shadow},
    )
    for (column,) in required.all():
        await session.execute(text(f'ALTER TABLE {shadow} ALTER COLUMN "{column}" DROP NOT NULL'))
    columns = {
        name
        for (name,) in (
            await session.execute(
                text(
                    "SELECT attname FROM pg_attribute WHERE attrelid = CAST(:shadow AS regclass) "
                    "AND attnum > 0 AND NOT attisdropped"
                ),
                {"shadow": shadow},
            )
        ).all()
    }
    triggers = (
        await session.execute(
            text(
                "SELECT pg_get_triggerdef(oid) FROM pg_trigger "
                "WHERE tgrelid = CAST(:real AS regclass) AND NOT tgisinternal "
                "AND (tgtype & 8) = 8"
            ),
            {"real": f"public.{table}"},
        )
    ).all()
    assert triggers, f"{table} has no BEFORE DELETE trigger to guard it"
    for (definition,) in triggers:
        function = re.search(r"EXECUTE FUNCTION (?:public\.)?(\w+)\(", definition)
        assert function and function.group(1) in GUARDED_FUNCTIONS, definition
        await session.execute(
            text(re.sub(r" ON \S+ ", f" ON pg_temp.{shadow} ", definition, count=1))
        )
    return shadow, columns


async def insert_row(
    session: AsyncSession, shadow: str, columns: set[str], organization_id: UUID | None
) -> None:
    values: dict[str, object] = {}
    if "organization_id" in columns:
        values["organization_id"] = organization_id
    if "status" in columns:
        values["status"] = "approved"  # a status every status-dependent trigger protects
    names = ", ".join(values) or "id"
    placeholders = ", ".join(f":{name}" for name in values) or "DEFAULT"
    if not values and "id" not in columns:
        raise AssertionError(f"{shadow} has no id to insert")
    await session.execute(text(f"INSERT INTO {shadow} ({names}) VALUES ({placeholders})"), values)


async def delete_rows(
    session: AsyncSession, shadow: str, columns: set[str], organization_id: UUID | None
) -> int | None:
    """Rows deleted, or None when the trigger refused."""
    if "organization_id" not in columns:
        where = "true"
    elif organization_id is None:
        where = "organization_id IS NULL"
    else:
        where = "organization_id = :organization_id"
    try:
        async with session.begin_nested():
            result = await session.execute(
                text(f"DELETE FROM {shadow} WHERE {where}"), {"organization_id": organization_id}
            )
            return int(result.rowcount or 0)  # type: ignore[attr-defined]
    except DBAPIError as error:
        assert getattr(error.orig, "sqlstate", None) == "23514", error
        return None


@pytest.mark.integration
@pytest.mark.anyio
@pytest.mark.parametrize("table", GOVERNED_TABLES)
async def test_governed_delete_is_allowed_only_for_the_organization_being_removed(
    organization_session_factory: async_sessionmaker[AsyncSession], table: str
) -> None:
    async with organization_session_factory.begin() as session:
        active = await make_organization(session, "active", status=OrganizationStatus.ACTIVE)
        offboarding = await make_organization(
            session, "offboarding", status=OrganizationStatus.OFFBOARDING
        )
        archived = await make_organization(session, "archived", status=OrganizationStatus.ARCHIVED)
        removing = await make_organization(
            session, "removing", status=OrganizationStatus.ARCHIVED, requested=True
        )
        removed = await make_organization(
            session, "removed", status=OrganizationStatus.ARCHIVED, requested=True, removed=True
        )
        shadow, columns = await shadow_of(session, table)

        if table in GLOBAL_TABLES or "organization_id" not in columns:
            # No organization to be "in removal": refused, whatever else is going on.
            await insert_row(session, shadow, columns, None)
            assert await delete_rows(session, shadow, columns, None) is None
            return

        for owner in (active, offboarding, archived, removing, removed):
            await insert_row(session, shadow, columns, owner)

        # Refused: an active or offboarding organization, an archived one nobody asked to
        # remove, and one whose removal already finished, even while another is being removed.
        for refused in (active, offboarding, archived, removed):
            assert await delete_rows(session, shadow, columns, refused) is None, (table, refused)
        # Allowed only for the organization whose removal is in progress, and only its rows.
        assert await delete_rows(session, shadow, columns, removing) == 1, table
        remaining = await session.scalar(text(f"SELECT count(*) FROM {shadow}"))
        assert remaining == 4


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_row_without_an_organization_is_never_deletable(
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """service_catalog may hold platform-wide rows (NULL organization); no removal owns them."""
    async with organization_session_factory.begin() as session:
        await make_organization(
            session, "removing", status=OrganizationStatus.ARCHIVED, requested=True
        )
        shadow, columns = await shadow_of(session, "service_catalog")
        await insert_row(session, shadow, columns, None)
        assert await delete_rows(session, shadow, columns, None) is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_no_session_setting_or_other_caller_state_can_open_the_guard(
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The decision is read from organizations; nothing a caller sets can substitute for it."""
    async with organization_session_factory.begin() as session:
        active = await make_organization(session, "active", status=OrganizationStatus.ACTIVE)
        shadow, columns = await shadow_of(session, "product_entitlements")
        await insert_row(session, shadow, columns, active)
        for name in ("lilos.organization_removal", "lilos.removal_organization_id"):
            await session.execute(
                text("SELECT set_config(:name, :value, true)"),
                {"name": name, "value": f"on {active}"},
            )
        assert await delete_rows(session, shadow, columns, active) is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_removal_state_only_exists_on_an_archived_organization(
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(DBAPIError):
        async with organization_session_factory.begin() as session:
            await make_organization(
                session, "live", status=OrganizationStatus.ACTIVE, requested=True
            )
