"""add mbti_type to users

Revision ID: 0005_add_user_mbti
Revises: 0004_users_profile
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_add_user_mbti"
down_revision = "0004_users_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mbti_type", sa.String(length=4), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "mbti_type")
