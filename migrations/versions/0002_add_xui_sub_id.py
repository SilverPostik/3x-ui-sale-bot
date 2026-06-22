"""add xui_sub_id to subscriptions

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("xui_sub_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "xui_sub_id")
