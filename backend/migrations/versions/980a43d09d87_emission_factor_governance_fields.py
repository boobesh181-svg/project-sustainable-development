"""Emission factor governance fields

Revision ID: 980a43d09d87
Revises: 6ab4e723094e
Create Date: 2026-01-01 10:38:11.535733

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '980a43d09d87'
down_revision: Union[str, Sequence[str], None] = '6ab4e723094e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ---- Emission factors: ISO-grade governance metadata ----
    # Use server defaults to avoid breaking existing rows and keep backward compatibility.
    op.add_column(
        "emission_factor",
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="National"),
    )
    op.add_column(
        "emission_factor",
        sa.Column("jurisdiction", sa.String(length=64), nullable=False, server_default="GLOBAL"),
    )
    op.add_column(
        "emission_factor",
        sa.Column(
            "methodology_reference",
            sa.String(length=255),
            nullable=False,
            server_default="unspecified",
        ),
    )

    # Drop server defaults after existing rows are satisfied; application should provide explicit values.
    op.alter_column("emission_factor", "source_type", server_default=None)
    op.alter_column("emission_factor", "jurisdiction", server_default=None)
    op.alter_column("emission_factor", "methodology_reference", server_default=None)

    op.create_check_constraint(
        "ck_emission_factor_source_type",
        "emission_factor",
        "source_type IN ('IPCC','National','EPD')",
    )
    op.create_check_constraint(
        "ck_emission_factor_jurisdiction_nonempty",
        "emission_factor",
        "char_length(jurisdiction) > 0",
    )
    op.create_check_constraint(
        "ck_emission_factor_methodology_ref_nonempty",
        "emission_factor",
        "char_length(methodology_reference) > 0",
    )

    # Update DB-level immutability enforcement to include new governance fields.
    # This prevents changing provenance metadata during activation/deactivation transitions.
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
                   OR NEW.source_type IS DISTINCT FROM OLD.source_type
                   OR NEW.jurisdiction IS DISTINCT FROM OLD.jurisdiction
                   OR NEW.methodology_reference IS DISTINCT FROM OLD.methodology_reference
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
                   OR NEW.source_type IS DISTINCT FROM OLD.source_type
                   OR NEW.jurisdiction IS DISTINCT FROM OLD.jurisdiction
                   OR NEW.methodology_reference IS DISTINCT FROM OLD.methodology_reference
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


def downgrade() -> None:
    """Downgrade schema."""

    # Restore prior version of the update-block trigger (without governance fields).
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

    op.drop_constraint("ck_emission_factor_methodology_ref_nonempty", "emission_factor", type_="check")
    op.drop_constraint("ck_emission_factor_jurisdiction_nonempty", "emission_factor", type_="check")
    op.drop_constraint("ck_emission_factor_source_type", "emission_factor", type_="check")

    op.drop_column("emission_factor", "methodology_reference")
    op.drop_column("emission_factor", "jurisdiction")
    op.drop_column("emission_factor", "source_type")
