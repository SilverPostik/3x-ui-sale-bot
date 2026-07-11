from sqlalchemy import BigInteger, String, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import mapped_column, Mapped, relationship
from database.models.base import Base, TimestampMixin
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.models.user import User


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    plan_months: Mapped[int] = mapped_column(Integer)  # 1, 3, 6, 12
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 3x-ui data
    xui_client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Одна или несколько inbound ID через запятую, например "1,2,3" —
    # клиент создан во всех этих inbound'ах с общим UUID/subId.
    xui_inbound_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    xui_sub_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # subId for subscription URL
    subscription_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    devices: Mapped[int] = mapped_column(Integer, default=1)
    inbound_type: Mapped[str] = mapped_column(String(32), default="vless_reality")

    # Notification flags
    notified_7d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_3d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_1d: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="subscriptions")

    @property
    def inbound_ids(self) -> list[int]:
        """Парсит xui_inbound_id ('1,2,3') в список int. Пусто -> []."""
        if not self.xui_inbound_id:
            return []
        return [int(x) for x in self.xui_inbound_id.split(",") if x.strip()]

    @staticmethod
    def format_inbound_ids(ids: list[int]) -> str:
        """Сериализует список inbound ID в строку для хранения в БД."""
        return ",".join(str(i) for i in ids)

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} user_id={self.user_id} active={self.is_active}>"
