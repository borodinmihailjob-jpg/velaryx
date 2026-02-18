"""Add indexes on FK columns for query performance.

Revision ID: 0003_add_fk_indexes
Revises: 0002_drop_unused
Create Date: 2026-02-18
"""

from alembic import op

revision = "0003_add_fk_indexes"
down_revision = "0002_drop_unused"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_birth_profiles_user_id", "birth_profiles", ["user_id"])
    op.create_index("ix_natal_charts_profile_id", "natal_charts", ["profile_id"])
    op.create_index("ix_daily_forecasts_user_id", "daily_forecasts", ["user_id"])
    op.create_index("ix_tarot_sessions_user_id", "tarot_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_tarot_sessions_user_id", table_name="tarot_sessions")
    op.drop_index("ix_daily_forecasts_user_id", table_name="daily_forecasts")
    op.drop_index("ix_natal_charts_profile_id", table_name="natal_charts")
    op.drop_index("ix_birth_profiles_user_id", table_name="birth_profiles")
