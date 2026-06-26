from sqlalchemy import BigInteger, String, Integer, ForeignKey, DateTime, Numeric
from sqlalchemy.orm import mapped_column, Mapped, relationship
from database.models.base import Base, TimestampMixin
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.models.user import User


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    plan_months: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)  # сумма в наименьших единицах (звёзды или копейки)
    currency: Mapped[str] = mapped_column(String(16), default="XTR")
    provider: Mapped[str] = mapped_column(String(32), default="telegram_stars")
    external_payment_id: Mapped[str | None] = mapped_column(String(256), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | paid | failed
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment id={self.id} provider={self.provider} status={self.status}>"
