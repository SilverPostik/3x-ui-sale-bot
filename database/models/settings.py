from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import mapped_column, Mapped
from database.models.base import Base, TimestampMixin


class Setting(Base, TimestampMixin):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    sent: Mapped[bool] = mapped_column(default=False)
