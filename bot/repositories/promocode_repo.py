from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.models.promocode import Promocode, PromocodeActivation
from datetime import datetime, timezone
from typing import Optional


class PromocodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_code(self, code: str) -> Optional[Promocode]:
        result = await self.session.execute(
            select(Promocode).where(Promocode.code == code.upper())
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[Promocode]:
        result = await self.session.execute(select(Promocode))
        return list(result.scalars().all())

    async def create(
        self,
        code: str,
        type: str,
        value: int,
        max_activations: Optional[int] = None,
        is_one_time: bool = False,
        expires_at: Optional[datetime] = None,
    ) -> Promocode:
        promo = Promocode(
            code=code.upper(),
            type=type,
            value=value,
            max_activations=max_activations,
            is_one_time=is_one_time,
            expires_at=expires_at,
        )
        self.session.add(promo)
        await self.session.commit()
        await self.session.refresh(promo)
        return promo

    async def update(self, promo: Promocode) -> Promocode:
        self.session.add(promo)
        await self.session.commit()
        await self.session.refresh(promo)
        return promo

    async def delete(self, promo: Promocode) -> None:
        await self.session.delete(promo)
        await self.session.commit()

    async def has_user_activated(self, promo_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            select(PromocodeActivation).where(
                and_(
                    PromocodeActivation.promocode_id == promo_id,
                    PromocodeActivation.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def record_activation(self, promo_id: int, user_id: int) -> PromocodeActivation:
        activation = PromocodeActivation(promocode_id=promo_id, user_id=user_id)
        self.session.add(activation)
        await self.session.commit()
        return activation
