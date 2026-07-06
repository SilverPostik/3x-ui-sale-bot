"""Add xui_inbound_ids column for multi-inbound subscriptions

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-06 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("xui_inbound_ids", sa.String(length=128), nullable=True),
    )
    # Переносим существующие значения xui_inbound_id (единый inbound) в новую колонку
    op.execute(
        "UPDATE subscriptions SET xui_inbound_ids = xui_inbound_id::text "
        "WHERE xui_inbound_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "xui_inbound_ids")
