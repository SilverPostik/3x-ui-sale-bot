import logging
from typing import Callable, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from bot.services.xui_client import xui_client

logger = logging.getLogger(__name__)


class XUIConnectionMiddleware(BaseMiddleware):
    """
    Перед каждым апдейтом проверяет соединение с 3x-ui и восстанавливает его.
    Это гарантирует что при любом действии пользователя клиент залогинен.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not xui_client._logged_in and not xui_client._api_token:
            logger.info("XUIMiddleware: сессия не активна, переподключаюсь...")
            ok = await xui_client.login()
            if not ok:
                logger.error("XUIMiddleware: не удалось подключиться к 3x-ui")
        return await handler(event, data)
