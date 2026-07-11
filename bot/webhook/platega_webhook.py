"""
Platega HTTP callback (webhook).
Подключается как отдельный aiohttp route рядом с ботом.

Настройка в личном кабинете Platega: Настройки → Callback URLs
URL: https://yourdomain.com/platega/notify

Provider отправляет заголовки X-MerchantId и X-Secret и JSON-тело:
{
  "id": "<transactionId>",
  "amount": 1000,
  "currency": "RUB",
  "status": "CONFIRMED" | "CANCELED" | "CHARGEBACKED",
  "paymentMethod": 2
}

Если endpoint не ответит 200 в течение 60 секунд, Platega повторит
запрос до 3 раз с интервалом 5 минут.
"""
import logging
from datetime import datetime, timezone
from aiohttp import web

from bot.services.platega_client import platega_client
from database.engine import AsyncSessionLocal
from bot.repositories import PaymentRepository
from bot.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


async def platega_notify(request: web.Request) -> web.Response:
    merchant_id = request.headers.get("X-MerchantId", "")
    secret = request.headers.get("X-Secret", "")

    if not platega_client.verify_callback_auth(merchant_id, secret):
        logger.warning("Platega callback: invalid X-MerchantId/X-Secret headers")
        return web.Response(status=403)

    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"Platega webhook parse error: {e}")
        return web.Response(status=400)

    logger.info(f"Platega callback: {data}")

    transaction_id = data.get("id", "")
    status = data.get("status", "")
    if not transaction_id:
        return web.Response(status=200)

    async with AsyncSessionLocal() as session:
        payment_repo = PaymentRepository(session)

        payment = await payment_repo.get_by_external_id(transaction_id)
        if not payment:
            logger.warning(f"Platega callback: unknown transaction_id={transaction_id}")
            return web.Response(status=200)

        if payment.status == "paid":
            logger.info(f"Duplicate Platega callback for payment {payment.id}")
            return web.Response(status=200)

        if status != "CONFIRMED":
            if status in ("CANCELED", "CHARGEBACKED"):
                payment.status = "failed"
                await payment_repo.update(payment)
                logger.info(f"Platega: payment {payment.id} status={status}")
            return web.Response(status=200)

        payment.status = "paid"
        payment.paid_at = datetime.now(timezone.utc)
        await payment_repo.update(payment)

        sub_service = SubscriptionService(session)
        sub = await sub_service.extend_subscription(payment.user_id, payment.plan_months)

        if sub:
            logger.info(f"Platega: subscription created for user {payment.user_id}")
            bot = request.app.get("bot")
            if bot:
                try:
                    await bot.send_message(
                        payment.user_id,
                        "✅ <b>Оплата подтверждена!</b>\n\nВаша подписка активирована.",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning(f"Cannot notify user {payment.user_id}: {e}")
        else:
            logger.error(f"Platega: failed to create subscription for user {payment.user_id}")

    return web.Response(status=200)


def setup_platega_webhook(app: web.Application) -> None:
    app.router.add_post("/platega/notify", platega_notify)
