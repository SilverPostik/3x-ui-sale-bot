import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import settings
from bot.handlers import get_main_router
from bot.middlewares import DbSessionMiddleware, UserMiddleware
from admin import admin_router
from scheduler import setup_scheduler
from bot.services.xui_client import xui_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middlewares
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(UserMiddleware())

    # Routers
    dp.include_router(get_main_router())
    dp.include_router(admin_router)

    # Scheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()

    # Login to 3x-ui
    ok = await xui_client.login()
    if not ok:
        logger.warning("Could not login to 3x-ui on startup — will retry on first request")

    # Start YooMoney webhook server (if enabled)
    webhook_runner = None
    if settings.ENABLE_YOOMONEY and settings.WEBHOOK_HOST:
        from aiohttp import web
        from bot.webhook.yoomoney_webhook import setup_yoomoney_webhook
        app = web.Application()
        app["bot"] = bot
        setup_yoomoney_webhook(app)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()
        webhook_runner = runner
        logger.info("YooMoney webhook listening on :8080")

    logger.info("Bot started")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        if webhook_runner:
            await webhook_runner.cleanup()
        await xui_client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
