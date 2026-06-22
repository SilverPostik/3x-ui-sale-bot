from sqlalchemy import BigInteger, String, Boolean
from sqlalchemy.orm import mapped_column, Mapped, relationship
from database.models.base import Base, TimestampMixin
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.models.subscription import Subscription
    from database.models.payment import Payment
    from database.models.promocode import PromocodeActivation


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram_id
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    discount_percent: Mapped[int] = mapped_column(default=0)  # from promo

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    promo_activations: Mapped[list["PromocodeActivation"]] = relationship(
        back_populates="user", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username}>"
