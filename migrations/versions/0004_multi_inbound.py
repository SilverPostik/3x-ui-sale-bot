"""multi-inbound support: xui_inbound_id integer -> string

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-11 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "subscriptions",
        "xui_inbound_id",
        existing_type=sa.Integer(),
        type_=sa.String(128),
        postgresql_using="xui_inbound_id::varchar",
    )


def downgrade() -> None:
    # Обратно в Integer безопасно только если для всех подписок хранился один ID.
    op.alter_column(
        "subscriptions",
        "xui_inbound_id",
        existing_type=sa.String(128),
        type_=sa.Integer(),
        postgresql_using="split_part(xui_inbound_id, ',', 1)::integer",
    )
