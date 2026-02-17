"""drop unused compat, wishlist and reservation tables

Revision ID: 0002_drop_unused
Revises: 0001_initial
Create Date: 2026-02-17 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_drop_unused"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("item_reservations")
    op.drop_table("wishlist_items")
    op.drop_table("wishlists")
    op.drop_table("compat_results")
    op.drop_table("compat_sessions")
    op.drop_table("compat_invites")


def downgrade() -> None:
    op.create_table(
        "compat_invites",
        sa.Column("token", sa.Text(), primary_key=True),
        sa.Column("inviter_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "compat_sessions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("inviter_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invitee_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invite_token", sa.Text(), sa.ForeignKey("compat_invites.token"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "compat_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("compat_sessions.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )

    op.create_table(
        "wishlists",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False, unique=True),
        sa.Column("public_token", sa.String(length=128), nullable=False, unique=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "wishlist_items",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("wishlist_id", sa.UUID(), sa.ForeignKey("wishlists.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("budget_cents", sa.Integer(), nullable=True),
    )

    op.create_table(
        "item_reservations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("item_id", sa.UUID(), sa.ForeignKey("wishlist_items.id"), nullable=False),
        sa.Column("reserver_tg_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reserver_name", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("item_id", "active", name="uq_item_active_reservation"),
    )
