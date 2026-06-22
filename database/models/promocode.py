from sqlalchemy import BigInteger, String, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import mapped_column, Mapped, relationship
from database.models.base import Base, TimestampMixin
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.models.user import User


class Promocode(Base, TimestampMixin):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(16))  # "days" | "discount"
    value: Mapped[int] = mapped_column(Integer)  # days or percent
    max_activations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activations_count: Mapped[int] = mapped_column(Integer, default=0)
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    activations: Mapped[list["PromocodeActivation"]] = relationship(
        back_populates="promocode", lazy="selectin"
    )


class PromocodeActivation(Base, TimestampMixin):
    __tablename__ = "promocode_activations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promocode_id: Mapped[int] = mapped_column(Integer, ForeignKey("promocodes.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))

    promocode: Mapped["Promocode"] = relationship(back_populates="activations")
    user: Mapped["User"] = relationship(back_populates="promo_activations")
