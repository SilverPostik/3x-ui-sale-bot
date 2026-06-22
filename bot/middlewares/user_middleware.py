from typing import Callable, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from bot.repositories import UserRepository


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if session and isinstance(event, Update):
            user = None
            if event.message:
                user = event.message.from_user
            elif event.callback_query:
                user = event.callback_query.from_user
            elif event.pre_checkout_query:
                user = event.pre_checkout_query.from_user

            if user:
                repo = UserRepository(session)
                db_user, _ = await repo.get_or_create(
                    user_id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                )
                data["db_user"] = db_user

        return await handler(event, data)
