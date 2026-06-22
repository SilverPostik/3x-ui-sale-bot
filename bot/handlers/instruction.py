from aiogram import Router
from aiogram.types import CallbackQuery

from bot.keyboards import instruction_kb, back_to_menu_kb
from config.texts import INSTRUCTION_CHOOSE_PLATFORM, INSTRUCTIONS

router = Router()


@router.callback_query(lambda c: c.data == "instruction")
async def cb_instruction(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        INSTRUCTION_CHOOSE_PLATFORM,
        reply_markup=instruction_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("instr_"))
async def cb_instruction_platform(callback: CallbackQuery) -> None:
    platform = callback.data.split("_", 1)[1]
    text = INSTRUCTIONS.get(platform)
    if not text:
        await callback.answer("Инструкция не найдена.", show_alert=True)
        return
    await callback.message.edit_text(
        text,
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
