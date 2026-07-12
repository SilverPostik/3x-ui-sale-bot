import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import PromocodeRepository, SubscriptionRepository
from bot.services.subscription_service import SubscriptionService
from database.models.subscription import Subscription

logger = logging.getLogger(__name__)


class PromocodeResult:
    def __init__(
        self,
        success: bool,
        error: Optional[str] = None,
        days_added: int = 0,
        discount_percent: int = 0,
    ) -> None:
        self.success = success
        self.error = error
        self.days_added = days_added
        self.discount_percent = discount_percent


class PromocodeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.promo_repo = PromocodeRepository(session)
        self.sub_repo = SubscriptionRepository(session)
        self.subscription_service = SubscriptionService(session)

    async def activate(self, code: str, user_id: int) -> PromocodeResult:
        promo = await self.promo_repo.get_by_code(code)
        if not promo or not promo.is_active:
            return PromocodeResult(False, error="invalid")

        now = datetime.now(timezone.utc)
        if promo.expires_at and promo.expires_at < now:
            return PromocodeResult(False, error="expired")

        if promo.max_activations and promo.activations_count >= promo.max_activations:
            return PromocodeResult(False, error="limit")

        if promo.is_one_time or promo.max_activations == 1:
            used = await self.promo_repo.has_user_activated(promo.id, user_id)
            if used:
                return PromocodeResult(False, error="already_used")

        if promo.type == "days":
            # Активацию засчитываем ТОЛЬКО после того, как подписка реально
            # создана/продлена в 3x-ui — иначе при сбое 3x-ui промокод сгорает
            # впустую, а пользователь так и остаётся без подписки.
            sub = await self.sub_repo.get_active(user_id)
            if sub:
                sub.expires_at = max(sub.expires_at, now) + timedelta(days=promo.value)
                await self.sub_repo.update(sub)
            else:
                new_sub = await self.subscription_service.create_promo_subscription(
                    user_id=user_id,
                    days=promo.value,
                )
                if not new_sub:
                    logger.error(f"Promocode days activation failed to create subscription for user {user_id}")
                    return PromocodeResult(False, error="server_error")

            await self.promo_repo.record_activation(promo.id, user_id)
            promo.activations_count += 1
            await self.promo_repo.update(promo)
            return PromocodeResult(True, days_added=promo.value)

        if promo.type == "discount":
            await self.promo_repo.record_activation(promo.id, user_id)
            promo.activations_count += 1
            await self.promo_repo.update(promo)
            return PromocodeResult(True, discount_percent=promo.value)

        return PromocodeResult(False, error="invalid")
