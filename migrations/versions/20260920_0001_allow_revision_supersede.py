"""Allow approved Content revisions to become superseded without mutating content."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260920_0001"
down_revision: str | Sequence[str] | None = "20260915_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_content_revision_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.status IN ('approved', 'published', 'superseded') THEN
                    RAISE EXCEPTION 'approved content revision is immutable'
                    USING ERRCODE = '23514';
                END IF;
                RETURN OLD;
            END IF;

            IF OLD.status = 'approved'
               AND NEW.status = 'superseded'
               AND (to_jsonb(NEW) - 'status') IS NOT DISTINCT FROM (to_jsonb(OLD) - 'status')
            THEN
                RETURN NEW;
            END IF;

            IF OLD.status IN ('approved', 'published', 'superseded') THEN
                RAISE EXCEPTION 'approved content revision is immutable'
                USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_content_revision_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status IN ('approved', 'published', 'superseded') THEN
                RAISE EXCEPTION 'approved content revision is immutable'
                USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
