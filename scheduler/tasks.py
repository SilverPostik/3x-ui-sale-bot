import logging
from datetime import datetime, timezone
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.engine import AsyncSessionLocal
from bot.repositories import SubscriptionRepository
from bot.services.subscription_service import SubscriptionService
from config.settings import settings
from config.texts import NOTIFY_7_DAYS, NOTIFY_3_DAYS, NOTIFY_1_DAY, NOTIFY_EXPIRED

logger = logging.getLogger(__name__)


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
    return scheduler
