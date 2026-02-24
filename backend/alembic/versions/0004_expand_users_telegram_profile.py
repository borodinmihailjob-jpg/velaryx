"""expand users with telegram profile fields

Revision ID: 0004_users_profile
Revises: 0003_add_fk_indexes
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_users_profile"
down_revision = "0003_add_fk_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("username", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("language_code", sa.String(length=16), nullable=True))
    op.add_column("users", sa.Column("is_premium", sa.Boolean(), nullable=True))
    op.add_column("users", sa.Column("allows_write_to_pm", sa.Boolean(), nullable=True))
    op.add_column("users", sa.Column("photo_url", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("telegram_user_payload", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_username", "users", ["username"])

    op.execute("UPDATE users SET updated_at = COALESCE(updated_at, created_at)")
    op.execute("UPDATE users SET last_seen_at = COALESCE(last_seen_at, created_at)")


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "telegram_user_payload")
    op.drop_column("users", "photo_url")
    op.drop_column("users", "allows_write_to_pm")
    op.drop_column("users", "is_premium")
    op.drop_column("users", "language_code")
    op.drop_column("users", "username")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
