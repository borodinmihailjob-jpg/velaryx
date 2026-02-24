"""add star_payments table

Revision ID: 0006_add_star_payments
Revises: 0005_add_user_mbti
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_add_star_payments"
down_revision = "0005_add_user_mbti"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "star_payments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("feature", sa.String(length=64), nullable=False),
        sa.Column("amount_stars", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("invoice_payload", sa.String(length=128), nullable=False),
        sa.Column("invoice_link", sa.Text(), nullable=True),
        sa.Column("telegram_payment_charge_id", sa.String(length=255), nullable=True),
        sa.Column("provider_payment_charge_id", sa.String(length=255), nullable=True),
        sa.Column("consumed_by_task_id", sa.String(length=128), nullable=True),
        sa.Column("meta_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("invoice_payload"),
        sa.UniqueConstraint("telegram_payment_charge_id"),
    )
    op.create_index("ix_star_payments_user_id", "star_payments", ["user_id"])
    op.create_index("ix_star_payments_tg_user_id", "star_payments", ["tg_user_id"])
    op.create_index("ix_star_payments_feature", "star_payments", ["feature"])
    op.create_index("ix_star_payments_status", "star_payments", ["status"])
    op.create_index("ix_star_payments_invoice_payload", "star_payments", ["invoice_payload"])


def downgrade() -> None:
    op.drop_index("ix_star_payments_invoice_payload", table_name="star_payments")
    op.drop_index("ix_star_payments_status", table_name="star_payments")
    op.drop_index("ix_star_payments_feature", table_name="star_payments")
    op.drop_index("ix_star_payments_tg_user_id", table_name="star_payments")
    op.drop_index("ix_star_payments_user_id", table_name="star_payments")
    op.drop_table("star_payments")

