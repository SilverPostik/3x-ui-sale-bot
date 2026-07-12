import logging
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import SubscriptionRepository
from bot.keyboards import connect_kb
from bot.utils.formatters import format_date, days_left, subscription_status
from bot.utils.qr import generate_qr
from bot.utils.tg import safe_edit_text
from config.texts import SUBSCRIPTION_INFO, NO_SUBSCRIPTION, ERROR_GENERIC

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "connect")
async def cb_connect(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        user_id = callback.from_user.id
        sub_repo = SubscriptionRepository(session)
        sub = await sub_repo.get_active(user_id)

        if not sub or not sub.subscription_url:
            await safe_edit_text(
                callback,
                NO_SUBSCRIPTION,
                reply_markup=connect_kb(has_subscription=False),
                parse_mode="HTML",
            )
            await callback.answer()
            return

        text = (
            f"{SUBSCRIPTION_INFO}\n\n"
            f"🔗 <code>{sub.subscription_url}</code>\n\n"
            f"⏳ Действует до: <b>{format_date(sub.expires_at)}</b>\n"
            f"🕐 Осталось дней: <b>{days_left(sub.expires_at)}</b>\n"
            f"🟢 Статус: <b>{subscription_status(sub.expires_at)}</b>"
        )

        qr_image = generate_qr(sub.subscription_url)

        # Удаление может не пройти (сообщение старше 48ч, уже удалено повторным
        # кликом и т.п.) — это не повод обрывать выдачу подписки без ответа.
        try:
            await callback.message.delete()
        except TelegramBadRequest as e:
            logger.warning(f"connect: couldn't delete previous message for user {user_id}: {e}")

        await callback.message.answer_photo(
            photo=qr_image,
            caption=text,
            reply_markup=connect_kb(has_subscription=True),
            parse_mode="HTML",
        )
        await callback.answer()

    except Exception as e:
        # Гарантируем, что кнопка в Telegram не "зависнет" даже при неожиданной ошибке
        logger.exception(f"cb_connect failed for user {callback.from_user.id}: {e}")
        try:
            await callback.answer(ERROR_GENERIC, show_alert=True)
        except Exception:
            pass
