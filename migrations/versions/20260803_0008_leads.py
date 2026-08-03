# ruff: noqa: E501
"""Create consent-aware Leads product with tenant RLS."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.products.leads.models import (
    CRMLeadMapping,
    Lead,
    LeadCommunication,
    LeadConsent,
    LeadSource,
    LeadStatusHistory,
    LeadSubmission,
    LeadSuppression,
)

revision = "20260803_0008"
down_revision: str | Sequence[str] | None = "20260803_0007"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, m.__table__)
    for m in (
        LeadSource,
        Lead,
        LeadSubmission,
        LeadConsent,
        LeadSuppression,
        LeadStatusHistory,
        LeadCommunication,
        CRMLeadMapping,
    )
)


def upgrade() -> None:
    for t in TABLES:
        t.create(bind=op.get_bind(), checkfirst=False)
    for table in (
        "lead_sources",
        "leads",
        "lead_submissions",
        "lead_consents",
        "lead_suppressions",
        "lead_status_history",
        "lead_communications",
        "crm_lead_mappings",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} USING (organization_id = NULLIF(current_setting('lilos.organization_id', true), '')::uuid) WITH CHECK (organization_id = NULLIF(current_setting('lilos.organization_id', true), '')::uuid)"
        )


def downgrade() -> None:
    for t in reversed(TABLES):
        t.drop(bind=op.get_bind(), checkfirst=False)
