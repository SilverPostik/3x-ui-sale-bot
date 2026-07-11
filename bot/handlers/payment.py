import logging
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    PreCheckoutQuery,
    Message,
    LabeledPrice,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import SettingsRepository
from bot.services.payment_service import PaymentService
from bot.services.subscription_service import SubscriptionService
from bot.keyboards import plans_kb, back_to_menu_kb
from config.texts import (
    CHOOSE_PLAN, PAYMENT_INVOICE_TITLE,
    PAYMENT_INVOICE_DESCRIPTION, PAYMENT_SUCCESS,
    PLAN_NAMES, NO_SLOTS_AVAILABLE,
)

logger = logging.getLogger(__name__)
router = Router()

PLAN_OPTIONS = [1, 3, 6, 12]


@router.callback_query(lambda c: c.data == "buy")
async def cb_buy(callback: CallbackQuery, session: AsyncSession) -> None:
    sub_service = SubscriptionService(session)
    if not await sub_service.has_capacity_for_new_user(callback.from_user.id):
        await callback.message.edit_text(
            NO_SLOTS_AVAILABLE,
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    settings_repo = SettingsRepository(session)
    prices = {m: await settings_repo.get_plan_price(m) for m in PLAN_OPTIONS}
    await callback.message.edit_text(
        CHOOSE_PLAN,
        reply_markup=plans_kb(prices),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("plan_"))
async def cb_select_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        months = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка выбора тарифа.", show_alert=True)
        return

    settings_repo = SettingsRepository(session)
    price = await settings_repo.get_plan_price(months)
    plan_name = PLAN_NAMES.get(months, f"{months} мес.")

    payment_service = PaymentService(session)
    pending = await payment_service.create_pending_payment(
        user_id=callback.from_user.id,
        plan_months=months,
        amount=price,
        provider="telegram_stars",
        currency="XTR",
    )

    await callback.message.answer_invoice(
        title=PAYMENT_INVOICE_TITLE.format(plan=plan_name),
        description=PAYMENT_INVOICE_DESCRIPTION.format(plan=plan_name),
        payload=f"payment:{pending.id}",
        currency="XTR",
        prices=[LabeledPrice(label=plan_name, amount=price)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, session: AsyncSession) -> None:
    payment_info = message.successful_payment
    charge_id = payment_info.telegram_payment_charge_id
    payload = payment_info.invoice_payload  # "payment:{id}"

    try:
        payment_id = int(payload.split(":")[1])
    except (IndexError, ValueError):
        logger.error(f"Invalid payment payload: {payload}")
        return

    service = PaymentService(session)
    sub = await service.confirm_payment(payment_id, charge_id)

    if sub:
        await message.answer(PAYMENT_SUCCESS, reply_markup=back_to_menu_kb(), parse_mode="HTML")
    else:
        await message.answer(
            "⚠️ Подписка не активирована. Пожалуйста, свяжитесь с поддержкой.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        logger.warning(f"Payment confirmation returned None for charge_id={charge_id}")
