"""
Хелпер для edit_text, который переживает сообщения с медиа (фото/QR-код).

Проблема: после выдачи подписки (bot/handlers/connect.py) бот отправляет
QR-код через answer_photo — у этого сообщения есть caption, а не text.
Telegram API не позволяет вызвать editMessageText на медиа-сообщении
(«There is no text in the message to edit»), из-за чего кнопки
«Инструкция» и «Главное меню» на этом сообщении переставали работать.

safe_edit_text пытается обычный edit_text, а если это невозможно —
удаляет старое сообщение и отправляет новое текстовое.
"""
import logging
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def safe_edit_text(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return
        if "no text in the message to edit" not in err and "can't be edited" not in err:
            logger.warning(f"safe_edit_text: unexpected edit_text error: {e}")

    # Сообщение — медиа (фото/видео/документ) или его больше нельзя редактировать:
    # удаляем и отправляем новое текстовое сообщение вместо него.
    try:
        await callback.message.delete()
    except TelegramBadRequest as e:
        logger.warning(f"safe_edit_text: couldn't delete message: {e}")

    await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
