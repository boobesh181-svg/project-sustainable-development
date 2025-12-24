"""MRV report DB enforcement: UUID actors + separation-of-duties + immutability.

Revision ID: 20251224_01
Revises: c19572fedd66
Create Date: 2025-12-24

"""

from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision = "20251224_01"
down_revision = "c19572fedd66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure Role rows exist before any demo/migrated users are inserted.
    # On a fresh database, tables exist but roles may not be seeded yet.
    op.execute(
        """
        INSERT INTO role (name) VALUES ('ADMIN'::role_name) ON CONFLICT (name) DO NOTHING;
        INSERT INTO role (name) VALUES ('PROJECT_MANAGER'::role_name) ON CONFLICT (name) DO NOTHING;
        INSERT INTO role (name) VALUES ('CONTRACTOR'::role_name) ON CONFLICT (name) DO NOTHING;
        INSERT INTO role (name) VALUES ('MRV_OFFICER'::role_name) ON CONFLICT (name) DO NOTHING;
        INSERT INTO role (name) VALUES ('SUPPLIER'::role_name) ON CONFLICT (name) DO NOTHING;
        INSERT INTO role (name) VALUES ('CITIZEN'::role_name) ON CONFLICT (name) DO NOTHING;
        """
    )

    # If legacy seed/demo MRV reports reference emails, ensure those emails exist
    # in the user table so they can be mapped to UUIDs.
    legacy_mrv_creator_id = uuid.uuid4()
    legacy_mrv_verifier_id = uuid.uuid4()
    legacy_mrv_approver_id = uuid.uuid4()

    op.execute(
        sa.text(
            """
            INSERT INTO "user" (id, email, hashed_password, full_name, is_active, role_id, created_at)
            SELECT :id, 'mrv@example.com', 'MIGRATED', 'MRV Creator (migrated)', true,
                   (SELECT id FROM role WHERE name = 'CONTRACTOR'::role_name),
                   now()
            WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE email = 'mrv@example.com');
            """
        ).bindparams(id=str(legacy_mrv_creator_id))
    )
    op.execute(
        sa.text(
            """
            INSERT INTO "user" (id, email, hashed_password, full_name, is_active, role_id, created_at)
            SELECT :id, 'verifier@example.com', 'MIGRATED', 'MRV Verifier (migrated)', true,
                   (SELECT id FROM role WHERE name = 'MRV_OFFICER'::role_name),
                   now()
            WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE email = 'verifier@example.com');
            """
        ).bindparams(id=str(legacy_mrv_verifier_id))
    )
    op.execute(
        sa.text(
            """
            INSERT INTO "user" (id, email, hashed_password, full_name, is_active, role_id, created_at)
            SELECT :id, 'approver@example.com', 'MIGRATED', 'MRV Approver (migrated)', true,
                   (SELECT id FROM role WHERE name = 'ADMIN'::role_name),
                   now()
            WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE email = 'approver@example.com');
            """
        ).bindparams(id=str(legacy_mrv_approver_id))
    )

    # 0) Pre-migration cleanup: convert legacy actor emails -> user UUID strings
    # Earlier seed/demo data stored emails in mrv_report.*_by. We map those emails
    # to "user".id before altering the column types.
    op.execute(
        """
        UPDATE mrv_report r
        SET created_by = u.id::text
        FROM "user" u
        WHERE r.created_by = u.email;
        """
    )
    op.execute(
        """
        UPDATE mrv_report r
        SET verified_by = u.id::text
        FROM "user" u
        WHERE r.verified_by = u.email;
        """
    )
    op.execute(
        """
        UPDATE mrv_report r
        SET approved_by = u.id::text
        FROM "user" u
        WHERE r.approved_by = u.email;
        """
    )

    # Fail fast if any remaining values are not UUID-castable.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM mrv_report
                WHERE created_by IS NULL
                   OR created_by !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            ) THEN
                RAISE EXCEPTION 'MRV migration blocked: mrv_report.created_by contains non-UUID values';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM mrv_report
                WHERE verified_by IS NOT NULL
                  AND verified_by !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            ) THEN
                RAISE EXCEPTION 'MRV migration blocked: mrv_report.verified_by contains non-UUID values';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM mrv_report
                WHERE approved_by IS NOT NULL
                  AND approved_by !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            ) THEN
                RAISE EXCEPTION 'MRV migration blocked: mrv_report.approved_by contains non-UUID values';
            END IF;
        END $$;
        """
    )

    # 1) Convert actor columns from varchar -> uuid
    # Use NULLIF for nullable columns to tolerate empty strings.
    op.execute(
        """
        ALTER TABLE mrv_report
            ALTER COLUMN created_by TYPE uuid USING created_by::uuid,
            ALTER COLUMN verified_by TYPE uuid USING NULLIF(verified_by, '')::uuid,
            ALTER COLUMN approved_by TYPE uuid USING NULLIF(approved_by, '')::uuid;
        """
    )

    # 2) Add FK constraints to user.id
    op.create_foreign_key(
        "fk_mrv_report_created_by_user",
        "mrv_report",
        "user",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_mrv_report_verified_by_user",
        "mrv_report",
        "user",
        ["verified_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_mrv_report_approved_by_user",
        "mrv_report",
        "user",
        ["approved_by"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 3) Add CHECK constraints for status/actors + separation of duties
    # Use raw SQL to avoid Alembic API/signature differences across environments.
    op.execute(
        """
        ALTER TABLE mrv_report
            ADD CONSTRAINT ck_mrv_verified_by_required
                CHECK ((status IN ('VERIFIED','APPROVED','LOCKED')) = (verified_by IS NOT NULL)),
            ADD CONSTRAINT ck_mrv_approved_by_required
                CHECK ((status IN ('APPROVED','LOCKED')) = (approved_by IS NOT NULL)),
            ADD CONSTRAINT ck_mrv_creator_ne_verifier
                CHECK (created_by IS DISTINCT FROM verified_by),
            ADD CONSTRAINT ck_mrv_creator_ne_approver
                CHECK (created_by IS DISTINCT FROM approved_by),
            ADD CONSTRAINT ck_mrv_verifier_ne_approver
                CHECK (verified_by IS DISTINCT FROM approved_by);
        """
    )

    # 4) DB-level immutability: once APPROVED, only allow APPROVED -> LOCKED transition.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mrv_report_block_edits_after_approval()
        RETURNS trigger AS $$
        BEGIN
            -- Fully immutable once LOCKED
            IF OLD.status = 'LOCKED' THEN
                RAISE EXCEPTION 'MRV report is LOCKED and immutable';
            END IF;

            -- After APPROVED: allow ONLY status APPROVED->LOCKED (and updated_at)
            IF OLD.status = 'APPROVED' THEN
                IF NOT (NEW.status = 'LOCKED' AND OLD.status = 'APPROVED') THEN
                    RAISE EXCEPTION 'MRV report is APPROVED and immutable (only APPROVED->LOCKED allowed)';
                END IF;

                -- Block any changes to business fields/actors/snapshots after approval
                IF NEW.project_id IS DISTINCT FROM OLD.project_id
                    OR NEW.reporting_period IS DISTINCT FROM OLD.reporting_period
                    OR NEW.emission_factor_id IS DISTINCT FROM OLD.emission_factor_id
                    OR NEW.sample_desc IS DISTINCT FROM OLD.sample_desc
                    OR NEW.parameter IS DISTINCT FROM OLD.parameter
                    OR NEW.value IS DISTINCT FROM OLD.value
                    OR NEW.total_co2e IS DISTINCT FROM OLD.total_co2e
                    OR NEW.certificate_path IS DISTINCT FROM OLD.certificate_path
                    OR NEW.emission_factor_version_snapshot IS DISTINCT FROM OLD.emission_factor_version_snapshot
                    OR NEW.emission_factor_hash_snapshot IS DISTINCT FROM OLD.emission_factor_hash_snapshot
                    OR NEW.emission_factor_value_snapshot IS DISTINCT FROM OLD.emission_factor_value_snapshot
                    OR NEW.created_by IS DISTINCT FROM OLD.created_by
                    OR NEW.verified_by IS DISTINCT FROM OLD.verified_by
                    OR NEW.approved_by IS DISTINCT FROM OLD.approved_by
                    OR NEW.created_at IS DISTINCT FROM OLD.created_at
                THEN
                    RAISE EXCEPTION 'MRV report is APPROVED and immutable (field modification blocked)';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_mrv_report_block_edits_after_approval ON mrv_report;
        CREATE TRIGGER trg_mrv_report_block_edits_after_approval
        BEFORE UPDATE ON mrv_report
        FOR EACH ROW
        EXECUTE FUNCTION mrv_report_block_edits_after_approval();
        """
    )

    # 5) Prevent deletes after APPROVED/LOCKED
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mrv_report_block_delete_after_approval()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status IN ('APPROVED','LOCKED') THEN
                RAISE EXCEPTION 'Cannot delete APPROVED/LOCKED MRV report';
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_mrv_report_block_delete_after_approval ON mrv_report;
        CREATE TRIGGER trg_mrv_report_block_delete_after_approval
        BEFORE DELETE ON mrv_report
        FOR EACH ROW
        EXECUTE FUNCTION mrv_report_block_delete_after_approval();
        """
    )


def downgrade() -> None:
    # Drop triggers/functions first
    op.execute("DROP TRIGGER IF EXISTS trg_mrv_report_block_delete_after_approval ON mrv_report;")
    op.execute("DROP FUNCTION IF EXISTS mrv_report_block_delete_after_approval;")

    op.execute("DROP TRIGGER IF EXISTS trg_mrv_report_block_edits_after_approval ON mrv_report;")
    op.execute("DROP FUNCTION IF EXISTS mrv_report_block_edits_after_approval;")

    # Drop check constraints
    op.execute(
        """
        ALTER TABLE mrv_report
            DROP CONSTRAINT IF EXISTS ck_mrv_verifier_ne_approver,
            DROP CONSTRAINT IF EXISTS ck_mrv_creator_ne_approver,
            DROP CONSTRAINT IF EXISTS ck_mrv_creator_ne_verifier,
            DROP CONSTRAINT IF EXISTS ck_mrv_approved_by_required,
            DROP CONSTRAINT IF EXISTS ck_mrv_verified_by_required;
        """
    )

    # Drop foreign keys
    op.drop_constraint("fk_mrv_report_approved_by_user", "mrv_report", type_="foreignkey")
    op.drop_constraint("fk_mrv_report_verified_by_user", "mrv_report", type_="foreignkey")
    op.drop_constraint("fk_mrv_report_created_by_user", "mrv_report", type_="foreignkey")

    # Convert columns back to string
    op.execute(
        """
        ALTER TABLE mrv_report
            ALTER COLUMN created_by TYPE varchar(100) USING created_by::text,
            ALTER COLUMN verified_by TYPE varchar(100) USING verified_by::text,
            ALTER COLUMN approved_by TYPE varchar(100) USING approved_by::text;
        """
    )
