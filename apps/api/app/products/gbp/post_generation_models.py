"""Persistence for AI-selected GBP post assets."""

from uuid import UUID

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GBPPostAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_post_assets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "post_revision_id"],
            ["gbp_post_revisions.organization_id", "gbp_post_revisions.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("post_revision_id", name="uq_gbp_post_asset_revision"),
        UniqueConstraint("organization_id", "id", name="uq_gbp_post_assets_org_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    post_revision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    provider_fetch_url: Mapped[str] = mapped_column(String(4000), nullable=False)
    metadata_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="selected")
