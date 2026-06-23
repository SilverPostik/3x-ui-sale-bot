from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import SubscriptionRepository, PaymentRepository, UserRepository
from bot.keyboards import profile_kb, back_to_menu_kb
from bot.utils.formatters import format_date, days_left, subscription_status
from config.texts import PROFILE_TEMPLATE, PLAN_NAMES, NO_SUBSCRIPTION

router = Router()


@router.callback_query(lambda c: c.data == "profile")
async def cb_profile(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = callback.from_user.id
    user_repo = UserRepository(session)
    sub_repo = SubscriptionRepository(session)

    user = await user_repo.get_by_id(user_id)
    sub = await sub_repo.get_active(user_id)
    registered_at = format_date(user.created_at) if user and user.created_at else "—"

    if sub:
        text = PROFILE_TEMPLATE.format(
            telegram_id=user_id,
            registered_at=registered_at,
            plan=PLAN_NAMES.get(sub.plan_months, f"{sub.plan_months} мес."),
            expires_at=format_date(sub.expires_at),
            days_left=days_left(sub.expires_at),
            status=subscription_status(sub.expires_at),
            devices=sub.devices,
        )
        kb = profile_kb()
    else:
        text = (
            f"👤 <b>Личный кабинет</b>\n\n"
            f"🆔 Telegram ID: <code>{user_id}</code>\n"
            f"📅 Дата регистрации: {registered_at}\n\n"
            f"{NO_SUBSCRIPTION}"
        )
        kb = back_to_menu_kb()

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "payment_history")
async def cb_payment_history(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = callback.from_user.id
    payment_repo = PaymentRepository(session)
    payments = await payment_repo.get_user_payments(user_id)

    if not payments:
        await callback.message.edit_text(
            "💳 <b>История платежей</b>\n\nПлатежей пока нет.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    lines = ["💳 <b>История платежей</b>\n"]
    for p in payments[:10]:
        date_str = format_date(p.paid_at) if p.paid_at else "—"
        currency = "⭐" if p.currency == "XTR" else "₽"
        lines.append(
            f"• {date_str} — "
            f"{PLAN_NAMES.get(p.plan_months, str(p.plan_months))} — "
            f"{p.amount_stars} {currency}"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
