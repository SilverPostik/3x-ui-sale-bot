"""Refactor payment model: rename amount_stars->amount, telegram_payment_charge_id->external_payment_id

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Переименовываем amount_stars -> amount
    op.alter_column("payments", "amount_stars", new_column_name="amount")

    # Переименовываем telegram_payment_charge_id -> external_payment_id
    # Сначала дропаем unique constraint, потом переименовываем, потом создаём новый
    op.drop_constraint("payments_telegram_payment_charge_id_key", "payments", type_="unique")
    op.alter_column("payments", "telegram_payment_charge_id", new_column_name="external_payment_id")
    op.create_unique_constraint("payments_external_payment_id_key", "payments", ["external_payment_id"])


def downgrade() -> None:
    op.drop_constraint("payments_external_payment_id_key", "payments", type_="unique")
    op.alter_column("payments", "external_payment_id", new_column_name="telegram_payment_charge_id")
    op.create_unique_constraint("payments_telegram_payment_charge_id_key", "payments", ["telegram_payment_charge_id"])
    op.alter_column("payments", "amount", new_column_name="amount_stars")
