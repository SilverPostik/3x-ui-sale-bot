import asyncio
import logging
import sys
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


async def run_migrations() -> None:
    """
    Применяет alembic-миграции (upgrade head) при каждом старте бота.
    Blocking-вызов уводим в отдельный поток через to_thread — у alembic
    внутри свой asyncio.run(), который нельзя вызвать из уже работающего loop.
    Безопасно на каждом старте: если схема уже актуальна, alembic ничего не делает.
    """
    def _upgrade() -> None:
        from pathlib import Path
        from alembic.config import Config
        from alembic import command
        project_root = Path(__file__).resolve().parent
        cfg = Config(str(project_root / "migrations" / "alembic.ini"))
        cfg.set_main_option("script_location", str(project_root / "migrations"))
        command.upgrade(cfg, "head")
        # alembic.ini подключает свой logging-конфиг через fileConfig(), у которого
        # ПО УМОЛЧАНИЮ disable_existing_loggers=True — он не просто меняет уровень
        # root-логгера, а помечает .disabled=True АБСОЛЮТНО ВСЕ уже созданные
        # логгеры (включая логгеры всех модулей бота, раз они создаются на импорте
        # module-level через logging.getLogger(__name__) до вызова main()).
        # Без этого восстановления бот замолкал бы полностью после старта.
        for _name in list(logging.Logger.manager.loggerDict.keys()):
            logging.getLogger(_name).disabled = False
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            force=True,
        )

    logger.info("Применяю alembic-миграции (upgrade head)...")
    try:
        await asyncio.to_thread(_upgrade)
        logger.info("Миграции применены ✓")
    except Exception as e:
        logger.error(f"Не удалось применить миграции: {e}")
        logger.error("Проверьте доступность БД (POSTGRES_HOST/POSTGRES_PORT/POSTGRES_PASSWORD в .env)")
        sys.exit(1)


async def main() -> None:
    await run_migrations()

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

    # ── Platega webhook (бот слушает 8080, nginx терминирует SSL на отдельном порту) ──
    webhook_runner = None
    if settings.ENABLE_PLATEGA and settings.WEBHOOK_HOST:
        from aiohttp import web
        from bot.webhook.platega_webhook import setup_platega_webhook

        app = web.Application()
        app["bot"] = bot
        setup_platega_webhook(app)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()
        webhook_runner = runner
        logger.info("Platega webhook listening on :8080 (nginx proxies HTTPS → here)")

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
