"""
Platega платёжный flow (СБП / Карта / Криптовалюта):
1. Пользователь выбирает способ оплаты и тариф.
2. Бот создаёт транзакцию через Platega API (POST /transaction/process)
   и отправляет пользователю ссылку на оплату (redirect).
3. Platega присылает callback на наш webhook при смене статуса —
   при CONFIRMED подписка выдаётся автоматически.
4. Дополнительно есть кнопка «Проверить оплату» — на случай, если
   callback ещё не дошёл, бот сам спросит статус через GET /transaction/{id}.
"""
import logging
from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import SettingsRepository
from bot.services.payment_service import PaymentService
from bot.services.platega_client import platega_client, new_external_id, PlategaError
from config.settings import settings
from config.texts import CHOOSE_PLAN, PLAN_NAMES, PAYMENT_SUCCESS
from bot.keyboards import back_to_menu_kb

logger = logging.getLogger(__name__)
router = Router()

PLAN_OPTIONS = [1, 3, 6, 12]

# Способ оплаты -> (код в Platega API, человекочитаемое название, provider для БД)
PLATEGA_METHODS = {
    "sbp": (settings.PLATEGA_METHOD_SBP, "СБП", "platega_sbp"),
    "card": (settings.PLATEGA_METHOD_CARD, "Банковская карта", "platega_card"),
    "crypto": (settings.PLATEGA_METHOD_CRYPTO, "Криптовалюта", "platega_crypto"),
}


def platega_plan_kb(method: str, prices: dict[int, int]) -> InlineKeyboardMarkup:
    buttons = []
    for months in PLAN_OPTIONS:
        buttons.append([
            InlineKeyboardButton(
                text=f"{PLAN_NAMES[months]} — {prices[months]} ₽",
                callback_data=f"pg_plan_{method}_{months}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(lambda c: c.data and c.data.startswith("buy_platega_"))
async def cb_buy_platega(callback: CallbackQuery, session: AsyncSession) -> None:
    method = callback.data.removeprefix("buy_platega_")
    if method not in PLATEGA_METHODS:
        await callback.answer("Неизвестный способ оплаты.", show_alert=True)
        return

    _, method_title, _ = PLATEGA_METHODS[method]
    settings_repo = SettingsRepository(session)
    prices = {m: await settings_repo.get_plan_price_rub(m) for m in PLAN_OPTIONS}
    await callback.message.edit_text(
        f"{CHOOSE_PLAN}\n\n💳 Способ оплаты: <b>{method_title}</b>",
        reply_markup=platega_plan_kb(method, prices),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("pg_plan_"))
async def cb_pg_select_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        _, _, method, months_str = callback.data.split("_", 3)
        months = int(months_str)
    except (IndexError, ValueError):
        await callback.answer("Ошибка выбора тарифа.", show_alert=True)
        return

    if method not in PLATEGA_METHODS:
        await callback.answer("Неизвестный способ оплаты.", show_alert=True)
        return

    payment_method_code, method_title, provider = PLATEGA_METHODS[method]

    settings_repo = SettingsRepository(session)
    price_rub = await settings_repo.get_plan_price_rub(months)
    plan_name = PLAN_NAMES.get(months, f"{months} мес.")

    payment_service = PaymentService(session)
    pending = await payment_service.create_pending_payment(
        user_id=callback.from_user.id,
        plan_months=months,
        amount=price_rub,
        provider=provider,
        currency="RUB",
    )

    try:
        tx = await platega_client.create_transaction(
            payment_method=payment_method_code,
            amount=float(price_rub),
            currency="RUB",
            description=f"Оплата подписки VPN, тариф {plan_name}",
            payload=str(pending.id),
            metadata={"userId": str(callback.from_user.id), "userName": f"@{callback.from_user.username}" if callback.from_user.username else ""},
        )
    except PlategaError as e:
        logger.error(f"Platega create_transaction failed for payment {pending.id}: {e}")
        await callback.message.edit_text(
            "⚠️ Не удалось создать платёж. Попробуйте позже или обратитесь в поддержку.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    # Сохраняем id транзакции Platega, чтобы сопоставить с callback/статусом
    pending.external_payment_id = tx.transaction_id
    await payment_service.payment_repo.update(pending)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить ({method_title})", url=tx.redirect)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"pg_check_{pending.id}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])

    await callback.message.edit_text(
        f"💳 <b>Оплата: {method_title}</b>\n\n"
        f"Тариф: <b>{plan_name}</b>\n"
        f"Сумма: <b>{price_rub} ₽</b>\n\n"
        f"Нажмите кнопку «Оплатить» и завершите оплату.\n\n"
        f"✅ Подписка активируется автоматически после подтверждения платежа.\n"
        f"Если оплата прошла, а подписка не активировалась — нажмите «Проверить оплату».",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("pg_check_"))
async def cb_pg_check_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        payment_id = int(callback.data.removeprefix("pg_check_"))
    except ValueError:
        await callback.answer("Ошибка.", show_alert=True)
        return

    payment_service = PaymentService(session)
    payment = await payment_service.payment_repo.get_by_id(payment_id)

    if not payment:
        await callback.answer("Платёж не найден.", show_alert=True)
        return

    if payment.status == "paid":
        await callback.message.edit_text(PAYMENT_SUCCESS, reply_markup=back_to_menu_kb(), parse_mode="HTML")
        await callback.answer()
        return

    if not payment.external_payment_id:
        await callback.answer("Платёж ещё не создан в Platega.", show_alert=True)
        return

    try:
        tx = await platega_client.get_transaction_status(payment.external_payment_id)
    except PlategaError as e:
        logger.error(f"Platega get_transaction_status failed for payment {payment_id}: {e}")
        await callback.answer("Не удалось проверить статус. Попробуйте чуть позже.", show_alert=True)
        return

    if tx.status == "CONFIRMED":
        sub = await payment_service.confirm_payment(payment.id, payment.external_payment_id)
        if sub:
            await callback.message.edit_text(PAYMENT_SUCCESS, reply_markup=back_to_menu_kb(), parse_mode="HTML")
        else:
            await callback.message.edit_text(
                "⚠️ Оплата подтверждена, но подписка не активировалась. Обратитесь в поддержку.",
                reply_markup=back_to_menu_kb(),
                parse_mode="HTML",
            )
        await callback.answer()
    elif tx.status in ("CANCELED", "CHARGEBACKED"):
        await callback.answer("❌ Платёж не был завершён успешно.", show_alert=True)
    else:
        await callback.answer("⏳ Платёж ещё в обработке. Подождите немного и проверьте снова.", show_alert=True)
