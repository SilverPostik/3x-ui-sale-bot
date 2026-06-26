"""
YooMoney HTTP-уведомление (webhook).
Подключается как отдельный aiohttp route рядом с ботом.

Настройка в YooMoney: https://yoomoney.ru/transfer/myservices/http-notification
URL: https://yourdomain.com/yoomoney/notify
"""
import logging
from datetime import datetime, timezone
from aiohttp import web
from bot.services.yoomoney_client import verify_notification
from database.engine import AsyncSessionLocal
from bot.repositories import PaymentRepository
from bot.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


async def yoomoney_notify(request: web.Request) -> web.Response:
    try:
        data = dict(await request.post())
    except Exception as e:
        logger.error(f"YooMoney webhook parse error: {e}")
        return web.Response(status=400)

    logger.info(f"YooMoney notification: {data}")

    if not verify_notification(data):
        logger.warning("YooMoney notification signature invalid")
        return web.Response(status=403)

    label = data.get("label", "")
    if not label:
        return web.Response(status=200)  # не наш платёж

    try:
        payment_id = int(label)
    except ValueError:
        return web.Response(status=200)

    operation_id = data.get("operation_id", "")

    async with AsyncSessionLocal() as session:
        payment_repo = PaymentRepository(session)

        # Защита от дублей
        existing = await payment_repo.get_by_external_id(operation_id)
        if existing:
            logger.info(f"Duplicate YooMoney notification operation_id={operation_id}")
            return web.Response(status=200)

        payment = await payment_repo.get_by_id(payment_id)
        if not payment or payment.status == "paid":
            return web.Response(status=200)

        payment.status = "paid"
        payment.external_payment_id = operation_id
        payment.paid_at = datetime.now(timezone.utc)
        await payment_repo.update(payment)

        sub_service = SubscriptionService(session)
        sub = await sub_service.extend_subscription(payment.user_id, payment.plan_months)

        if sub:
            logger.info(f"YooMoney: subscription created for user {payment.user_id}")
            bot = request.app.get("bot")
            if bot:
                try:
                    await bot.send_message(
                        payment.user_id,
                        "✅ <b>Оплата через ЮMoney подтверждена!</b>\n\nВаша подписка активирована.",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning(f"Cannot notify user {payment.user_id}: {e}")
        else:
            logger.error(f"YooMoney: failed to create subscription for user {payment.user_id}")

    return web.Response(status=200)


def setup_yoomoney_webhook(app: web.Application) -> None:
    app.router.add_post("/yoomoney/notify", yoomoney_notify)
