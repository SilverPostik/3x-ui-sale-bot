from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from database.models.payment import Payment
from datetime import datetime, timezone
from typing import Optional


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: int,
        plan_months: int,
        amount: int,
        currency: str = "XTR",
        provider: str = "telegram_stars",
    ) -> Payment:
        payment = Payment(
            user_id=user_id,
            plan_months=plan_months,
            amount=amount,
            currency=currency,
            provider=provider,
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_by_id(self, payment_id: int) -> Optional[Payment]:
        result = await self.session.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> Optional[Payment]:
        result = await self.session.execute(
            select(Payment).where(Payment.external_payment_id == external_id)
        )
        return result.scalar_one_or_none()

    # backward compat alias (используется в confirm_payment для Stars)
    async def get_by_charge_id(self, charge_id: str) -> Optional[Payment]:
        return await self.get_by_external_id(charge_id)

    async def update(self, payment: Payment) -> Payment:
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_user_payments(self, user_id: int) -> list[Payment]:
        result = await self.session.execute(
            select(Payment)
            .where(and_(Payment.user_id == user_id, Payment.status == "paid"))
            .order_by(Payment.paid_at.desc())
        )
        return list(result.scalars().all())

    async def sum_revenue(self, since: Optional[datetime] = None, currency: str = "XTR") -> int:
        query = select(func.sum(Payment.amount)).where(
            and_(Payment.status == "paid", Payment.currency == currency)
        )
        if since:
            query = query.where(Payment.paid_at >= since)
        result = await self.session.execute(query)
        return result.scalar_one() or 0

    async def revenue_today(self, currency: str = "XTR") -> int:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.sum_revenue(since=start, currency=currency)

    async def revenue_month(self, currency: str = "XTR") -> int:
        start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return await self.sum_revenue(since=start, currency=currency)
