from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Bot
    BOT_TOKEN: str

    # Database
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "vpnbot"
    POSTGRES_USER: str = "vpnbot"
    POSTGRES_PASSWORD: str

    # 3x-ui
    THREEXUI_URL: str
    THREEXUI_USERNAME: str
    THREEXUI_PASSWORD: str
    REALITY_INBOUND_ID: int = 1
    DEFAULT_LIMIT_IP: int = 1  # max devices per subscription

    # Payments
    TELEGRAM_STARS_PROVIDER_TOKEN: str = ""
    YOOMONEY_WALLET: str = ""         # Номер кошелька YooMoney получателя
    YOOMONEY_SECRET: str = ""          # Секрет для проверки уведомлений
    ENABLE_YOOMONEY: bool = False      # Включить ЮMoney как способ оплаты
    WEBHOOK_HOST: str = ""             # https://yourdomain.com (для YooMoney webhook)

    # Admin
    ADMIN_IDS: List[int] = []

    # Support
    SUPPORT_USERNAME: str = "support"

    # Notifications
    NOTIFY_7_DAYS: bool = True
    NOTIFY_3_DAYS: bool = True
    NOTIFY_1_DAY: bool = True
    DISABLE_EXPIRED_USERS: bool = True

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
