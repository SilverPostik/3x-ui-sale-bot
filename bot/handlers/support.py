from aiogram import Router
from aiogram.types import CallbackQuery

from bot.keyboards import back_to_menu_kb
from config.settings import settings
from config.texts import SUPPORT_TEXT

router = Router()


@router.callback_query(lambda c: c.data == "support")
async def cb_support(callback: CallbackQuery) -> None:
    text = SUPPORT_TEXT.format(username=settings.SUPPORT_USERNAME)
    await callback.message.edit_text(
        text, reply_markup=back_to_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()
