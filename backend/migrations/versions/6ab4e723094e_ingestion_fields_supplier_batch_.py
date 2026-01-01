"""Ingestion fields supplier batch delivery ts evidence geo

Revision ID: 6ab4e723094e
Revises: 20251227_03
Create Date: 2026-01-01 10:13:09.831878

"""
from typing import Sequence, Union

import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ab4e723094e'
down_revision: Union[str, Sequence[str], None] = '20251227_03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ---- evidence optional geo fields ----
    op.add_column("evidence", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("evidence", sa.Column("lon", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_evidence_valid_lat",
        "evidence",
        "lat IS NULL OR (lat >= -90 AND lat <= 90)",
    )
    op.create_check_constraint(
        "ck_evidence_valid_lon",
        "evidence",
        "lon IS NULL OR (lon >= -180 AND lon <= 180)",
    )

    # Evidence immutability: treat new geo fields as immutable core fields.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION evidence_block_illegal_updates() RETURNS trigger AS $$
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                RAISE EXCEPTION 'Evidence rows are append-only and cannot be deleted';
            END IF;

            IF (OLD.verified_at IS NOT NULL) THEN
                RAISE EXCEPTION 'Evidence is verified and immutable';
            END IF;

            IF NEW.upload_type IS DISTINCT FROM OLD.upload_type
               OR NEW.storage_path IS DISTINCT FROM OLD.storage_path
               OR NEW.sha256 IS DISTINCT FROM OLD.sha256
               OR NEW.size_bytes IS DISTINCT FROM OLD.size_bytes
               OR NEW.content_type IS DISTINCT FROM OLD.content_type
               OR NEW.original_filename IS DISTINCT FROM OLD.original_filename
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.created_by IS DISTINCT FROM OLD.created_by
               OR NEW.report_id IS DISTINCT FROM OLD.report_id
               OR NEW.material_token_id IS DISTINCT FROM OLD.material_token_id
               OR NEW.lat IS DISTINCT FROM OLD.lat
               OR NEW.lon IS DISTINCT FROM OLD.lon
            THEN
                RAISE EXCEPTION 'Evidence core fields are immutable';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # ---- material token ingestion fields ----
    op.add_column("material_token", sa.Column("supplier_id", sa.UUID(), nullable=True))
    op.add_column("material_token", sa.Column("batch_id", sa.String(length=100), nullable=True))
    op.add_column(
        "material_token", sa.Column("delivery_timestamp", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_material_token_supplier",
        "material_token",
        "supplier",
        ["supplier_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Backfill legacy data so the stricter redemption completeness constraint can be applied.
    # - delivery_timestamp: use redeemed_at if present, else NOW()
    # - supplier_id: map from existing supplier_name to supplier.id; create supplier rows if missing
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            UPDATE material_token
            SET delivery_timestamp = COALESCE(delivery_timestamp, redeemed_at, NOW())
            WHERE redeemed = true AND delivery_timestamp IS NULL
            """
        )
    )

    # Best-effort mapping for existing rows.
    bind.execute(
        sa.text(
            """
            UPDATE material_token mt
            SET supplier_id = s.id
            FROM supplier s
            WHERE mt.supplier_id IS NULL
              AND mt.supplier_name = s.name
            """
        )
    )

    missing_supplier_names = (
        bind.execute(
            sa.text(
                """
                SELECT DISTINCT mt.supplier_name
                FROM material_token mt
                LEFT JOIN supplier s ON s.name = mt.supplier_name
                WHERE mt.redeemed = true
                  AND mt.supplier_id IS NULL
                  AND s.id IS NULL
                """
            )
        )
        .scalars()
        .all()
    )

    for supplier_name in missing_supplier_names:
        bind.execute(
            sa.text(
                """
                INSERT INTO supplier (id, name, partnership_discount, total_value_supplied)
                VALUES (:id, :name, :partnership_discount, :total_value_supplied)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "name": supplier_name,
                "partnership_discount": 0,
                "total_value_supplied": 0,
            },
        )

    # Re-run mapping after creating any missing suppliers.
    bind.execute(
        sa.text(
            """
            UPDATE material_token mt
            SET supplier_id = s.id
            FROM supplier s
            WHERE mt.supplier_id IS NULL
              AND mt.supplier_name = s.name
            """
        )
    )

    # Tighten redemption completeness constraint to require supplier_id + delivery_timestamp.
    op.drop_constraint("ck_material_token_redemption_complete", "material_token", type_="check")
    op.create_check_constraint(
        "ck_material_token_redemption_complete",
        "material_token",
        "redeemed = false OR (redeemed_at IS NOT NULL AND delivery_timestamp IS NOT NULL AND supplier_id IS NOT NULL AND delivery_lat IS NOT NULL AND delivery_lon IS NOT NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Revert redemption completeness constraint.
    op.drop_constraint("ck_material_token_redemption_complete", "material_token", type_="check")
    op.create_check_constraint(
        "ck_material_token_redemption_complete",
        "material_token",
        "redeemed = false OR (redeemed_at IS NOT NULL AND delivery_lat IS NOT NULL AND delivery_lon IS NOT NULL)",
    )

    op.drop_constraint("fk_material_token_supplier", "material_token", type_="foreignkey")
    op.drop_column("material_token", "delivery_timestamp")
    op.drop_column("material_token", "batch_id")
    op.drop_column("material_token", "supplier_id")

    # Revert evidence immutability trigger core-field list (remove lat/lon).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION evidence_block_illegal_updates() RETURNS trigger AS $$
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                RAISE EXCEPTION 'Evidence rows are append-only and cannot be deleted';
            END IF;

            IF (OLD.verified_at IS NOT NULL) THEN
                RAISE EXCEPTION 'Evidence is verified and immutable';
            END IF;

            IF NEW.upload_type IS DISTINCT FROM OLD.upload_type
               OR NEW.storage_path IS DISTINCT FROM OLD.storage_path
               OR NEW.sha256 IS DISTINCT FROM OLD.sha256
               OR NEW.size_bytes IS DISTINCT FROM OLD.size_bytes
               OR NEW.content_type IS DISTINCT FROM OLD.content_type
               OR NEW.original_filename IS DISTINCT FROM OLD.original_filename
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.created_by IS DISTINCT FROM OLD.created_by
               OR NEW.report_id IS DISTINCT FROM OLD.report_id
               OR NEW.material_token_id IS DISTINCT FROM OLD.material_token_id
            THEN
                RAISE EXCEPTION 'Evidence core fields are immutable';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.drop_constraint("ck_evidence_valid_lon", "evidence", type_="check")
    op.drop_constraint("ck_evidence_valid_lat", "evidence", type_="check")
    op.drop_column("evidence", "lon")
    op.drop_column("evidence", "lat")
