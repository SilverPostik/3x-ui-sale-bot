from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.promocode_service import PromocodeService
from bot.keyboards import back_to_menu_kb
from config.texts import (
    PROMO_ENTER, PROMO_INVALID, PROMO_EXPIRED,
    PROMO_LIMIT, PROMO_ALREADY_USED, PROMO_SERVER_ERROR,
    PROMO_SUCCESS_DAYS, PROMO_SUCCESS_DISCOUNT,
)

router = Router()


class PromoStates(StatesGroup):
    waiting_code = State()


@router.callback_query(lambda c: c.data == "promo")
async def cb_promo(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(PROMO_ENTER, reply_markup=back_to_menu_kb(), parse_mode="HTML")
    await state.set_state(PromoStates.waiting_code)
    await callback.answer()


@router.message(PromoStates.waiting_code)
async def handle_promo_code(message: Message, state: FSMContext, session: AsyncSession) -> None:
    code = message.text.strip() if message.text else ""
    service = PromocodeService(session)
    result = await service.activate(code, message.from_user.id)
    await state.clear()

    if not result.success:
        error_map = {
            "invalid": PROMO_INVALID,
            "expired": PROMO_EXPIRED,
            "limit": PROMO_LIMIT,
            "already_used": PROMO_ALREADY_USED,
            "server_error": PROMO_SERVER_ERROR,
        }
        text = error_map.get(result.error, PROMO_INVALID)
    elif result.days_added:
        text = PROMO_SUCCESS_DAYS.format(days=result.days_added)
    else:
        text = PROMO_SUCCESS_DISCOUNT.format(discount=result.discount_percent)

    await message.answer(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")
