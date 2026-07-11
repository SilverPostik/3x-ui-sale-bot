from typing import List, Annotated
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode
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
    THREEXUI_USERNAME: str = ""
    THREEXUI_PASSWORD: str = ""
    THREEXUI_API_TOKEN: str = ""
    THREEXUI_SUB_PORT: int = 2096  # порт для ссылок подписки (не путать с портом панели)
    # Один или несколько inbound ID через запятую: "1" или "1,2,3".
    # Клиент будет создан сразу во всех указанных inbound'ах (один UUID/подписка на все).
    REALITY_INBOUND_ID: Annotated[List[int], NoDecode] = [1]
    DEFAULT_LIMIT_IP: int = 1  # max devices per subscription

    # Ограничение количества пользователей с активной платной подпиской.
    # 0 — без ограничений. При достижении лимита новым пользователям недоступна покупка
    # (продление подписки уже существующим клиентам лимитом не блокируется).
    MAX_ACTIVE_SUBSCRIPTIONS: int = 0

    # Payments
    TELEGRAM_STARS_PROVIDER_TOKEN: str = ""

    # Platega.io (СБП, карточный эквайринг, криптовалюта)
    ENABLE_PLATEGA: bool = False        # Включить Platega как способ оплаты
    PLATEGA_MERCHANT_ID: str = ""       # X-MerchantId (выдаётся менеджером/ЛК Platega)
    PLATEGA_SECRET: str = ""            # X-Secret (выдаётся менеджером/ЛК Platega)
    # Коды способов оплаты (PaymentMethodInt в API Platega).
    # 2 (СБП) и 13 (крипта) подтверждены документацией Platega.
    # Код карточного эквайринга индивидуален для мерчанта — уточните у
    # вашего менеджера Platega и при необходимости измените значение ниже.
    PLATEGA_METHOD_SBP: int = 2
    PLATEGA_METHOD_CARD: int = 1
    PLATEGA_METHOD_CRYPTO: int = 13
    WEBHOOK_HOST: str = ""              # https://yourdomain.com (для Platega callback)

    # Admin
    ADMIN_IDS: Annotated[List[int], NoDecode] = []

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

    @field_validator("REALITY_INBOUND_ID", mode="before")
    @classmethod
    def parse_reality_inbound_id(cls, v):
        if isinstance(v, str):
            ids = [int(x.strip()) for x in v.split(",") if x.strip()]
            if not ids:
                raise ValueError("REALITY_INBOUND_ID: список не может быть пустым")
            return ids
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
