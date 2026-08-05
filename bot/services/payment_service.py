import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import PaymentRepository, SettingsRepository
from bot.services.subscription_service import SubscriptionService
from database.models.payment import Payment
from database.models.subscription import Subscription

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.payment_repo = PaymentRepository(session)
        self.settings_repo = SettingsRepository(session)
        self.sub_service = SubscriptionService(session)

    async def get_plan_price_stars(self, months: int) -> int:
        return await self.settings_repo.get_plan_price(months)

    async def get_plan_price_rub(self, months: int) -> int:
        return await self.settings_repo.get_plan_price_rub(months)

    async def create_pending_payment(
        self,
        user_id: int,
        plan_months: int,
        amount: int,
        provider: str = "telegram_stars",
        currency: str = "XTR",
    ) -> Payment:
        """Создаёт pending-платёж. Единственный метод для всех провайдеров."""
        return await self.payment_repo.create(
            user_id=user_id,
            plan_months=plan_months,
            amount=amount,
            currency=currency,
            provider=provider,
        )

    async def confirm_payment(
        self,
        payment_id: int,
        external_payment_id: str,
    ) -> Optional[Subscription]:
        """
        Подтверждает оплату и создаёт/продлевает подписку.
        Идемпотентен — возвращает None если платёж уже был обработан ранее
        (проверка по payment.status, а не по external_payment_id: для Platega
        external_payment_id проставляется на pending-платёж СРАЗУ при создании
        транзакции, ещё до реальной оплаты — поиск по нему нашёл бы саму же
        текущую запись и ложно считал бы её "уже обработанным дубликатом",
        из-за чего confirm_payment всегда возвращал None на кнопке
        «Проверить оплату», даже при первом реальном подтверждении).
        """
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment or payment.status == "paid":
            return None

        payment.status = "paid"
        payment.external_payment_id = external_payment_id
        payment.paid_at = datetime.now(timezone.utc)
        await self.payment_repo.update(payment)

        sub = await self.sub_service.extend_subscription(payment.user_id, payment.plan_months)
        if not sub:
            logger.error(f"confirm_payment: subscription creation failed for user {payment.user_id}")
            return None

        return sub
