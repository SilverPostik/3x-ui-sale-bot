import logging
from datetime import datetime, timezone
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.engine import AsyncSessionLocal
from bot.repositories import SubscriptionRepository, PaymentRepository
from bot.services.subscription_service import SubscriptionService
from bot.services.xui_client import xui_client
from config.settings import settings
from config.texts import NOTIFY_7_DAYS, NOTIFY_3_DAYS, NOTIFY_1_DAY, NOTIFY_EXPIRED

logger = logging.getLogger(__name__)

# Простой флаг в памяти процесса, чтобы не слать одно и то же предупреждение
# админу каждые 2 минуты, пока панель лежит — только один раз на инцидент.
_xui_down_alert_sent = False


async def check_subscriptions(bot: Bot) -> None:
    """
    Daily task: send expiry notifications and disable expired subscriptions.
    """
    async with AsyncSessionLocal() as session:
        sub_repo = SubscriptionRepository(session)

        # Notifications
        notification_map = [
            (7, "notified_7d", NOTIFY_7_DAYS, settings.NOTIFY_7_DAYS),
            (3, "notified_3d", NOTIFY_3_DAYS, settings.NOTIFY_3_DAYS),
            (1, "notified_1d", NOTIFY_1_DAY, settings.NOTIFY_1_DAY),
        ]

        for days, flag_attr, text, enabled in notification_map:
            if not enabled:
                continue
            expiring = await sub_repo.get_expiring_soon(days)
            for sub in expiring:
                if getattr(sub, flag_attr):
                    continue
                try:
                    await bot.send_message(sub.user_id, text, parse_mode="HTML")
                    setattr(sub, flag_attr, True)
                    await sub_repo.update(sub)
                except Exception as e:
                    logger.warning(f"Failed to notify user {sub.user_id}: {e}")

        # Disable expired
        if settings.DISABLE_EXPIRED_USERS:
            sub_service = SubscriptionService(session)
            affected = await sub_service.disable_expired()
            for user_id in affected:
                try:
                    await bot.send_message(user_id, NOTIFY_EXPIRED, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"Failed to notify expired user {user_id}: {e}")


async def retry_pending_xui_payments(bot: Bot) -> None:
    """
    Каждые 5 минут: находит платежи, которые провайдер уже подтвердил, но
    применить в 3x-ui не удалось (панель была недоступна в момент коллбэка,
    см. bot/webhook/platega_webhook.py), и повторяет продление подписки.
    """
    async with AsyncSessionLocal() as session:
        payment_repo = PaymentRepository(session)
        pending = await payment_repo.get_by_status("confirmed_pending_xui")
        if not pending:
            return

        logger.info(f"retry_pending_xui_payments: в очереди {len(pending)} платежей")
        sub_service = SubscriptionService(session)

        for payment in pending:
            sub = await sub_service.extend_subscription(payment.user_id, payment.plan_months)
            if not sub:
                logger.warning(
                    f"retry_pending_xui_payments: payment={payment.id} "
                    f"user={payment.user_id} — всё ещё не удалось, попробуем в след. раз"
                )
                continue

            payment.status = "paid"
            payment.paid_at = datetime.now(timezone.utc)
            await payment_repo.update(payment)
            logger.info(f"retry_pending_xui_payments: payment={payment.id} успешно применён")
            try:
                await bot.send_message(
                    payment.user_id,
                    "✅ <b>Оплата подтверждена!</b>\n\nВаша подписка активирована.",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Cannot notify user {payment.user_id}: {e}")


async def check_xui_connection(bot: Bot) -> None:
    """
    Каждые 2 минуты проверяет, жива ли панель 3x-ui, и шлёт админам сообщение
    сразу при обрыве — а не когда об этом напишет расстроенный пользователь.
    При восстановлении шлёт отдельное сообщение "снова в порядке".
    """
    global _xui_down_alert_sent
    ok = await xui_client.ping()

    if not ok and not _xui_down_alert_sent:
        _xui_down_alert_sent = True
        logger.error("check_xui_connection: панель 3x-ui не отвечает")
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    "🔴 <b>3x-ui не отвечает</b>\n\nПроверьте сервер (systemctl status x-ui / логи).",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Cannot notify admin {admin_id}: {e}")

    elif ok and _xui_down_alert_sent:
        _xui_down_alert_sent = False
        logger.info("check_xui_connection: соединение с 3x-ui восстановлено")
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, "🟢 Соединение с 3x-ui восстановлено.")
            except Exception as e:
                logger.warning(f"Cannot notify admin {admin_id}: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        check_subscriptions,
        trigger="cron",
        hour=9,
        minute=0,
        kwargs={"bot": bot},
        id="check_subscriptions",
        replace_existing=True,
    )
    scheduler.add_job(
        retry_pending_xui_payments,
        trigger="interval",
        minutes=5,
        kwargs={"bot": bot},
        id="retry_pending_xui_payments",
        replace_existing=True,
    )
    scheduler.add_job(
        check_xui_connection,
        trigger="interval",
        minutes=2,
        kwargs={"bot": bot},
        id="check_xui_connection",
        replace_existing=True,
    )
    return scheduler
