from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.models.subscription import Subscription
from datetime import datetime, timezone
from typing import Optional


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self, user_id: int) -> Optional[Subscription]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Subscription).where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.is_active == True,
                    Subscription.expires_at > now,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, sub_id: int) -> Optional[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        plan_months: int,
        expires_at: datetime,
        xui_client_id: str,
        xui_inbound_id: str,
        subscription_url: str,
        xui_sub_id: str = "",
        inbound_type: str = "vless_reality",
        devices: int = 1,
    ) -> Subscription:
        sub = Subscription(
            user_id=user_id,
            plan_months=plan_months,
            expires_at=expires_at,
            xui_client_id=xui_client_id,
            xui_inbound_id=xui_inbound_id,
            xui_sub_id=xui_sub_id,
            subscription_url=subscription_url,
            inbound_type=inbound_type,
            devices=devices,
        )
        self.session.add(sub)
        await self.session.commit()
        await self.session.refresh(sub)
        return sub

    async def update(self, sub: Subscription) -> Subscription:
        self.session.add(sub)
        await self.session.commit()
        await self.session.refresh(sub)
        return sub

    async def get_expiring_soon(self, days: int) -> list[Subscription]:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=days)
        result = await self.session.execute(
            select(Subscription).where(
                and_(
                    Subscription.is_active == True,
                    Subscription.expires_at > now,
                    Subscription.expires_at <= threshold,
                )
            )
        )
        return list(result.scalars().all())

    async def get_expired(self) -> list[Subscription]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Subscription).where(
                and_(
                    Subscription.is_active == True,
                    Subscription.expires_at <= now,
                )
            )
        )
        return list(result.scalars().all())

    async def count_active(self) -> int:
        from sqlalchemy import func
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(func.count(Subscription.id)).where(
                and_(Subscription.is_active == True, Subscription.expires_at > now)
            )
        )
        return result.scalar_one()

    async def get_last(self, user_id: int) -> Optional[Subscription]:
        """Последняя подписка пользователя (любая, включая истёкшую)."""
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
