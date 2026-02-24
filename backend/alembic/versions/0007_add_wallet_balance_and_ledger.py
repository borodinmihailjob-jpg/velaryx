"""add wallet balance and ledger

Revision ID: 0007_wallet_balance
Revises: 0006_add_star_payments
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_wallet_balance"
down_revision = "0006_add_star_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("wallet_balance", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("users", "wallet_balance", server_default=None)

    op.create_table(
        "wallet_ledger",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("delta_stars", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("feature", sa.String(length=64), nullable=True),
        sa.Column("star_payment_id", sa.UUID(), sa.ForeignKey("star_payments.id"), nullable=True),
        sa.Column("related_ledger_id", sa.UUID(), sa.ForeignKey("wallet_ledger.id"), nullable=True),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("meta_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("star_payment_id"),
    )
    op.create_index("ix_wallet_ledger_user_id", "wallet_ledger", ["user_id"])
    op.create_index("ix_wallet_ledger_tg_user_id", "wallet_ledger", ["tg_user_id"])
    op.create_index("ix_wallet_ledger_kind", "wallet_ledger", ["kind"])
    op.create_index("ix_wallet_ledger_feature", "wallet_ledger", ["feature"])
    op.create_index("ix_wallet_ledger_star_payment_id", "wallet_ledger", ["star_payment_id"])
    op.create_index("ix_wallet_ledger_related_ledger_id", "wallet_ledger", ["related_ledger_id"])


def downgrade() -> None:
    op.drop_index("ix_wallet_ledger_related_ledger_id", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_star_payment_id", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_feature", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_kind", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_tg_user_id", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_user_id", table_name="wallet_ledger")
    op.drop_table("wallet_ledger")
    op.drop_column("users", "wallet_balance")
