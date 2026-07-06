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
    xui_inbound_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # legacy, оставлено для совместимости
    xui_inbound_ids: Mapped[str | None] = mapped_column(String(128), nullable=True)  # "1,2,3" — все inbound'ы клиента
    xui_sub_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # subId for subscription URL
    subscription_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    devices: Mapped[int] = mapped_column(Integer, default=1)
    inbound_type: Mapped[str] = mapped_column(String(32), default="vless_reality")

    # Notification flags
    notified_7d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_3d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_1d: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} user_id={self.user_id} active={self.is_active}>"

    @property
    def inbound_id_list(self) -> list[int]:
        """Список ID inbound'ов, в которые выдан клиент."""
        if self.xui_inbound_ids:
            return [int(x) for x in self.xui_inbound_ids.split(",") if x.strip()]
        if self.xui_inbound_id is not None:
            return [self.xui_inbound_id]
        return []
