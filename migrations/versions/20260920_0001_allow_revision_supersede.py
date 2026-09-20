"""Allow approved Content revisions to transition to superseded/published status only.

Revision: 20260920_0001
Revises: 20260915_0001
"""

from collections.abc import Sequence

from alembic import op

revision = "20260920_0001"
down_revision: str | Sequence[str] | None = "20260915_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION prevent_content_revision_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND OLD.status IN ('approved','published','superseded') THEN
                RAISE EXCEPTION 'approved content revision is immutable' USING ERRCODE='23514';
            END IF;

            IF TG_OP = 'UPDATE' AND OLD.status IN ('approved','published','superseded') THEN
                IF ROW(
                    NEW.organization_id,
                    NEW.content_item_id,
                    NEW.revision_number,
                    NEW.body,
                    NEW.frontmatter,
                    NEW.content_hash,
                    NEW.created_by_type,
                    NEW.created_by_user_id,
                    NEW.ai_execution_id,
                    NEW.approved_fact_revision_ids,
                    NEW.validation_document,
                    NEW.editorial_approved_by,
                    NEW.client_approved_by,
                    NEW.approved_at,
                    NEW.created_at
                ) IS DISTINCT FROM ROW(
                    OLD.organization_id,
                    OLD.content_item_id,
                    OLD.revision_number,
                    OLD.body,
                    OLD.frontmatter,
                    OLD.content_hash,
                    OLD.created_by_type,
                    OLD.created_by_user_id,
                    OLD.ai_execution_id,
                    OLD.approved_fact_revision_ids,
                    OLD.validation_document,
                    OLD.editorial_approved_by,
                    OLD.client_approved_by,
                    OLD.approved_at,
                    OLD.created_at
                ) THEN
                    RAISE EXCEPTION 'approved content revision is immutable' USING ERRCODE='23514';
                END IF;

                IF OLD.status = 'approved' AND NEW.status IN ('approved','published','superseded') THEN
                    RETURN NEW;
                END IF;
                IF OLD.status = 'published' AND NEW.status = 'published' THEN
                    RETURN NEW;
                END IF;
                IF OLD.status = 'superseded' AND NEW.status = 'superseded' THEN
                    RETURN NEW;
                END IF;

                RAISE EXCEPTION 'invalid immutable content revision status transition'
                    USING ERRCODE='23514';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION prevent_content_revision_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status IN ('approved','published','superseded') THEN
                RAISE EXCEPTION 'approved content revision is immutable' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
