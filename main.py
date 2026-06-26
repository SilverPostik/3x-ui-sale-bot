import asyncio
import logging
import os
import ssl
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
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Путь к сертификатам (монтируется через docker volume)
CERT_BASE = "/etc/letsencrypt/live"


def _build_ssl_context(domain: str) -> ssl.SSLContext | None:
    """Строит SSL-контекст если сертификаты есть на диске."""
    cert = f"{CERT_BASE}/{domain}/fullchain.pem"
    key  = f"{CERT_BASE}/{domain}/privkey.pem"
    if not (os.path.exists(cert) and os.path.exists(key)):
        logger.warning(f"SSL сертификаты не найдены: {cert} — webhook запустится на HTTP :8080")
        return None
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(cert, key)
    logger.info(f"SSL сертификат загружен: {domain}")
    return ctx


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(UserMiddleware())

    dp.include_router(get_main_router())
    dp.include_router(admin_router)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    logger.info(f"Connecting to 3x-ui at {settings.THREEXUI_URL} ...")
    if await xui_client.ping():
        logger.info("3x-ui connection OK ✓")
    else:
        logger.warning(
            "3x-ui connection FAILED — бот будет повторно пытаться при первой попытке создания подписки. "
            "Проверьте THREEXUI_URL, THREEXUI_USERNAME, THREEXUI_PASSWORD или THREEXUI_API_TOKEN в .env"
        )

    # ── YooMoney webhook ──────────────────────────────────────────────────────
    webhook_runner = None
    if settings.ENABLE_YOOMONEY and settings.WEBHOOK_HOST:
        from aiohttp import web
        from bot.webhook.yoomoney_webhook import setup_yoomoney_webhook

        app = web.Application()
        app["bot"] = bot
        setup_yoomoney_webhook(app)

        runner = web.AppRunner(app)
        await runner.setup()

        # Определяем — есть SSL или нет
        domain = settings.WEBHOOK_HOST.removeprefix("https://").removeprefix("http://").split(":")[0]
        ssl_ctx = _build_ssl_context(domain)

        if ssl_ctx:
            site = web.TCPSite(runner, "0.0.0.0", 443, ssl_context=ssl_ctx)
            logger.info("YooMoney webhook listening on :443 (HTTPS)")
        else:
            site = web.TCPSite(runner, "0.0.0.0", 8080)
            logger.info("YooMoney webhook listening on :8080 (HTTP, без SSL)")

        await site.start()
        webhook_runner = runner

    logger.info("Bot started, polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        if webhook_runner:
            await webhook_runner.cleanup()
        await xui_client.close()
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
