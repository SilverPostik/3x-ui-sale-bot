from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from config.texts import WELCOME, NO_SLOTS_AVAILABLE
from bot.keyboards import main_menu_kb, back_to_menu_kb
from bot.utils.tg import safe_edit_text

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    await safe_edit_text(callback, WELCOME, reply_markup=main_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "buy_choose")
async def cb_buy_choose(callback: CallbackQuery, session: AsyncSession) -> None:
    from bot.keyboards.main_kb import payment_method_kb
    from bot.services.subscription_service import SubscriptionService

    sub_service = SubscriptionService(session)
    if not await sub_service.has_capacity_for_new_user(callback.from_user.id):
        await safe_edit_text(callback, NO_SLOTS_AVAILABLE, reply_markup=back_to_menu_kb(), parse_mode="HTML")
        await callback.answer()
        return

    await safe_edit_text(
        callback,
        "💳 <b>Выберите способ оплаты:</b>",
        reply_markup=payment_method_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
