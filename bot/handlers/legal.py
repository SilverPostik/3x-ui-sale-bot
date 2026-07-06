"""
Раздел «Документы»: политика конфиденциальности, пользовательское соглашение
и тарифы. Эти документы должны быть постоянно доступны пользователю из
главного меню бота (требование платёжного провайдера).
"""
from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import docs_menu_kb, docs_back_kb
from bot.repositories import SettingsRepository
from config.texts import DOCS_MENU_TEXT, PLAN_NAMES
from config.legal import PRIVACY_POLICY, TERMS_OF_SERVICE, PRICING_INTRO, PRICING_ROW, PRICING_FOOTER

router = Router()


@router.callback_query(lambda c: c.data == "docs")
async def cb_docs_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        DOCS_MENU_TEXT, reply_markup=docs_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "docs_privacy")
async def cb_docs_privacy(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        PRIVACY_POLICY, reply_markup=docs_back_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "docs_terms")
async def cb_docs_terms(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        TERMS_OF_SERVICE, reply_markup=docs_back_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "docs_pricing")
async def cb_docs_pricing(callback: CallbackQuery, session: AsyncSession) -> None:
    settings_repo = SettingsRepository(session)

    rows = []
    for months in (1, 3, 6, 12):
        stars = await settings_repo.get_plan_price(months)
        rub = await settings_repo.get_plan_price_rub(months)
        rows.append(PRICING_ROW.format(plan=PLAN_NAMES[months], stars=stars, rub=rub))

    text = PRICING_INTRO + "\n\n" + "\n".join(rows) + PRICING_FOOTER.format(extra_methods="")

    await callback.message.edit_text(
        text, reply_markup=docs_back_kb(), parse_mode="HTML"
    )
    await callback.answer()
