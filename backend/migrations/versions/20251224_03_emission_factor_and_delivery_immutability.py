"""Add governance/immutability controls for emission factors and delivery evidence.

- Adds user-id foreign keys for creator/verifier attribution without breaking
  existing string fields (keeps created_by / verified_by as labels).
- Enforces append-only / immutable behavior at the DB level via triggers.

This supports regulator-grade reproducibility and chain-of-custody requirements.

Revision ID: 20251224_03
Revises: 20251224_02
Create Date: 2025-12-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20251224_03"
down_revision = "20251224_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Emission factors: add creator FK (nullable for legacy rows) ---
    op.add_column(
        "emission_factor",
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_emission_factor_created_by_user",
        "emission_factor",
        "user",
        ["created_by_user_id"],
        ["id"],
    )

    # Best-effort backfill from legacy created_by string (email)
    op.execute(
        """
        UPDATE emission_factor ef
        SET created_by_user_id = u.id
        FROM "user" u
        WHERE ef.created_by_user_id IS NULL
          AND u.email = ef.created_by;
        """
    )

    # DB-level immutability/append-only enforcement for emission factors.
    # Rules:
    # - No UPDATE except flipping is_active False->True (activation) or True->False (deactivation)
    # - No DELETE (append-only)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION emission_factor_block_update() RETURNS trigger AS $$
        BEGIN
            -- Allow deactivation of an active factor (only is_active may change)
            IF (OLD.is_active = TRUE AND NEW.is_active = FALSE) THEN
                IF NEW.material_code IS DISTINCT FROM OLD.material_code
                   OR NEW.material_name IS DISTINCT FROM OLD.material_name
                   OR NEW.version IS DISTINCT FROM OLD.version
                   OR NEW.co2e_per_unit IS DISTINCT FROM OLD.co2e_per_unit
                   OR NEW.unit IS DISTINCT FROM OLD.unit
                   OR NEW.valid_from IS DISTINCT FROM OLD.valid_from
                   OR NEW.valid_to IS DISTINCT FROM OLD.valid_to
                   OR NEW.factor_hash IS DISTINCT FROM OLD.factor_hash
                   OR NEW.created_at IS DISTINCT FROM OLD.created_at
                   OR NEW.created_by IS DISTINCT FROM OLD.created_by
                   OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id
                THEN
                    RAISE EXCEPTION 'Emission factor rows are immutable; only is_active may flip to deactivate';
                END IF;
                RETURN NEW;
            END IF;

            -- Allow activation of an inactive factor (only is_active may change)
            IF (OLD.is_active = FALSE AND NEW.is_active = TRUE) THEN
                IF NEW.material_code IS DISTINCT FROM OLD.material_code
                   OR NEW.material_name IS DISTINCT FROM OLD.material_name
                   OR NEW.version IS DISTINCT FROM OLD.version
                   OR NEW.co2e_per_unit IS DISTINCT FROM OLD.co2e_per_unit
                   OR NEW.unit IS DISTINCT FROM OLD.unit
                   OR NEW.valid_from IS DISTINCT FROM OLD.valid_from
                   OR NEW.valid_to IS DISTINCT FROM OLD.valid_to
                   OR NEW.factor_hash IS DISTINCT FROM OLD.factor_hash
                   OR NEW.created_at IS DISTINCT FROM OLD.created_at
                   OR NEW.created_by IS DISTINCT FROM OLD.created_by
                   OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id
                THEN
                    RAISE EXCEPTION 'Emission factor rows are immutable; activation cannot modify factor data';
                END IF;
                RETURN NEW;
            END IF;

            RAISE EXCEPTION 'Emission factor rows are immutable; create a new version instead of updating';
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_emission_factor_block_update ON emission_factor;
        CREATE TRIGGER trg_emission_factor_block_update
        BEFORE UPDATE ON emission_factor
        FOR EACH ROW
        EXECUTE FUNCTION emission_factor_block_update();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION emission_factor_block_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Emission factor rows are append-only and cannot be deleted';
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_emission_factor_block_delete ON emission_factor;
        CREATE TRIGGER trg_emission_factor_block_delete
        BEFORE DELETE ON emission_factor
        FOR EACH ROW
        EXECUTE FUNCTION emission_factor_block_delete();
        """
    )

    # --- Delivery verification: add actor FKs (nullable for legacy rows) ---
    op.add_column(
        "delivery_verification",
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_delivery_verification_created_by_user",
        "delivery_verification",
        "user",
        ["created_by_user_id"],
        ["id"],
    )

    op.add_column(
        "delivery_verification",
        sa.Column(
            "verified_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_delivery_verification_verified_by_user",
        "delivery_verification",
        "user",
        ["verified_by_user_id"],
        ["id"],
    )

    # Best-effort backfill verifier id from legacy verified_by string (email)
    op.execute(
        """
        UPDATE delivery_verification dv
        SET verified_by_user_id = u.id
        FROM "user" u
        WHERE dv.verified_by_user_id IS NULL
          AND u.email = dv.verified_by;
        """
    )

    # DB-level immutability for delivery verification.
    # Rules:
    # - Once is_verified = TRUE, row is immutable
    # - Deletion is not allowed (append-only evidence)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION delivery_verification_block_update() RETURNS trigger AS $$
        BEGIN
            IF (OLD.is_verified = TRUE) THEN
                RAISE EXCEPTION 'Delivery verification is verified and immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_delivery_verification_block_update ON delivery_verification;
        CREATE TRIGGER trg_delivery_verification_block_update
        BEFORE UPDATE ON delivery_verification
        FOR EACH ROW
        EXECUTE FUNCTION delivery_verification_block_update();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION delivery_verification_block_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Delivery verification rows are append-only and cannot be deleted';
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_delivery_verification_block_delete ON delivery_verification;
        CREATE TRIGGER trg_delivery_verification_block_delete
        BEFORE DELETE ON delivery_verification
        FOR EACH ROW
        EXECUTE FUNCTION delivery_verification_block_delete();
        """
    )


def downgrade() -> None:
    # Drop delivery triggers/functions
    op.execute("DROP TRIGGER IF EXISTS trg_delivery_verification_block_delete ON delivery_verification;")
    op.execute("DROP TRIGGER IF EXISTS trg_delivery_verification_block_update ON delivery_verification;")
    op.execute("DROP FUNCTION IF EXISTS delivery_verification_block_delete();")
    op.execute("DROP FUNCTION IF EXISTS delivery_verification_block_update();")

    op.drop_constraint(
        "fk_delivery_verification_verified_by_user",
        "delivery_verification",
        type_="foreignkey",
    )
    op.drop_column("delivery_verification", "verified_by_user_id")

    op.drop_constraint(
        "fk_delivery_verification_created_by_user",
        "delivery_verification",
        type_="foreignkey",
    )
    op.drop_column("delivery_verification", "created_by_user_id")

    # Drop emission factor triggers/functions
    op.execute("DROP TRIGGER IF EXISTS trg_emission_factor_block_delete ON emission_factor;")
    op.execute("DROP TRIGGER IF EXISTS trg_emission_factor_block_update ON emission_factor;")
    op.execute("DROP FUNCTION IF EXISTS emission_factor_block_delete();")
    op.execute("DROP FUNCTION IF EXISTS emission_factor_block_update();")

    op.drop_constraint(
        "fk_emission_factor_created_by_user",
        "emission_factor",
        type_="foreignkey",
    )
    op.drop_column("emission_factor", "created_by_user_id")
