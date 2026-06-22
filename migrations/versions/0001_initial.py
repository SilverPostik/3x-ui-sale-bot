"""initial

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("full_name", sa.String(256), nullable=True),
        sa.Column("is_banned", sa.Boolean(), nullable=False, default=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_months", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("xui_client_id", sa.String(64), nullable=True),
        sa.Column("xui_inbound_id", sa.Integer(), nullable=True),
        sa.Column("subscription_url", sa.String(512), nullable=True),
        sa.Column("devices", sa.Integer(), nullable=False, default=1),
        sa.Column("inbound_type", sa.String(32), nullable=False, default="vless_reality"),
        sa.Column("notified_7d", sa.Boolean(), nullable=False, default=False),
        sa.Column("notified_3d", sa.Boolean(), nullable=False, default=False),
        sa.Column("notified_1d", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_months", sa.Integer(), nullable=False),
        sa.Column("amount_stars", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(16), nullable=False, default="XTR"),
        sa.Column("provider", sa.String(32), nullable=False, default="telegram_stars"),
        sa.Column("telegram_payment_charge_id", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_payment_charge_id"),
    )

    op.create_table(
        "promocodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("max_activations", sa.Integer(), nullable=True),
        sa.Column("activations_count", sa.Integer(), nullable=False, default=0),
        sa.Column("is_one_time", sa.Boolean(), nullable=False, default=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_promocodes_code", "promocodes", ["code"])

    op.create_table(
        "promocode_activations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("promocode_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["promocode_id"], ["promocodes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "settings",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("sent", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("settings")
    op.drop_table("promocode_activations")
    op.drop_index("ix_promocodes_code", table_name="promocodes")
    op.drop_table("promocodes")
    op.drop_table("payments")
    op.drop_table("subscriptions")
    op.drop_table("users")
