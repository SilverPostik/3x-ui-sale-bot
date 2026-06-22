"""
ЮMoney платёжный flow:
1. Пользователь выбирает тариф → бот отправляет ссылку на оплату YooMoney Quickpay.
2. После оплаты YooMoney делает HTTP POST на вебхук-эндпоинт.
3. Вебхук проверяет подпись, помечает платёж оплаченным, создаёт подписку.

Для получения уведомлений нужно настроить вебхук в личном кабинете YooMoney:
  Настройки → Переводы и платежи → Уведомления HTTP → ваш URL /yoomoney/notify
"""
import logging
from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import SettingsRepository
from bot.services.payment_service import PaymentService
from bot.services.yoomoney_client import build_payment_url
from config.settings import settings
from config.texts import CHOOSE_PLAN, PLAN_NAMES
from bot.keyboards import plans_kb, back_to_menu_kb

logger = logging.getLogger(__name__)
router = Router()

PLAN_OPTIONS = [1, 3, 6, 12]


def yoomoney_plan_kb(prices: dict[int, int]) -> InlineKeyboardMarkup:
    buttons = []
    for months in PLAN_OPTIONS:
        buttons.append([
            InlineKeyboardButton(
                text=f"{PLAN_NAMES[months]} — {prices[months]} ₽",
                callback_data=f"ym_plan_{months}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(lambda c: c.data == "buy_yoomoney")
async def cb_buy_yoomoney(callback: CallbackQuery, session: AsyncSession) -> None:
    settings_repo = SettingsRepository(session)
    prices = {m: await settings_repo.get_plan_price_rub(m) for m in PLAN_OPTIONS}
    await callback.message.edit_text(
        CHOOSE_PLAN,
        reply_markup=yoomoney_plan_kb(prices),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("ym_plan_"))
async def cb_ym_select_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        months = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка выбора тарифа.", show_alert=True)
        return

    settings_repo = SettingsRepository(session)
    price_rub = await settings_repo.get_plan_price_rub(months)
    plan_name = PLAN_NAMES.get(months, f"{months} мес.")

    payment_service = PaymentService(session)
    pending = await payment_service.create_pending_payment(
        user_id=callback.from_user.id,
        plan_months=months,
        amount=price_rub,
        provider="yoomoney",
        currency="RUB",
    )

    pay_url = build_payment_url(
        receiver=settings.YOOMONEY_WALLET,
        amount=float(price_rub),
        label=str(pending.id),
        comment=f"VPN {plan_name}",
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через ЮMoney", url=pay_url)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"ym_check_{pending.id}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])

    await callback.message.edit_text(
        f"💳 <b>Оплата через ЮMoney</b>\n\n"
        f"Тариф: <b>{plan_name}</b>\n"
        f"Сумма: <b>{price_rub} ₽</b>\n\n"
        f"1. Нажмите кнопку «Оплатить».\n"
        f"2. После оплаты нажмите «Я оплатил».\n\n"
        f"⚠️ Подписка активируется автоматически после подтверждения платежа.",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("ym_check_"))
async def cb_ym_check(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Пользователь нажал 'Я оплатил'. Проверяем статус платежа в БД.
    Если вебхук уже пришёл — активируем подписку. Иначе — просим подождать.
    """
    try:
        payment_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка.", show_alert=True)
        return

    from bot.repositories import PaymentRepository
    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_by_id(payment_id)

    if not payment:
        await callback.answer("Платёж не найден.", show_alert=True)
        return

    if payment.status == "paid":
        await callback.message.edit_text(
            "✅ <b>Оплата подтверждена!</b>\n\nВаша подписка активирована.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
    else:
        await callback.answer(
            "⏳ Оплата ещё не подтверждена. Подождите 1-2 минуты и попробуйте снова.",
            show_alert=True,
        )
