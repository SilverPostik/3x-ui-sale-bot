from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.settings import Setting
from typing import Optional

DEFAULT_PRICES_STARS = {"price_1": "100", "price_3": "250", "price_6": "450", "price_12": "800"}
DEFAULT_PRICES_RUB   = {"price_rub_1": "149", "price_rub_3": "399", "price_rub_6": "699", "price_rub_12": "1199"}


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        result = await self.session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        return setting.value if setting else default

    async def set(self, key: str, value: str, description: Optional[str] = None) -> Setting:
        result = await self.session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value, description=description)
            self.session.add(setting)
        await self.session.commit()
        await self.session.refresh(setting)
        return setting

    async def get_plan_price(self, months: int) -> int:
        """Цена в Telegram Stars"""
        key = f"price_{months}"
        value = await self.get(key, DEFAULT_PRICES_STARS.get(key, "100"))
        return int(value)

    async def get_plan_price_rub(self, months: int) -> int:
        """Цена в рублях (Platega — СБП/карта/крипта)"""
        key = f"price_rub_{months}"
        value = await self.get(key, DEFAULT_PRICES_RUB.get(key, "149"))
        return int(value)

    async def ensure_defaults(self) -> None:
        for key, value in {**DEFAULT_PRICES_STARS, **DEFAULT_PRICES_RUB}.items():
            if await self.get(key) is None:
                await self.set(key, value)
