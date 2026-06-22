from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import SubscriptionRepository
from bot.keyboards import connect_kb
from bot.utils.formatters import format_date, days_left, subscription_status
from bot.utils.qr import generate_qr
from config.texts import SUBSCRIPTION_INFO, NO_SUBSCRIPTION

router = Router()


@router.callback_query(lambda c: c.data == "connect")
async def cb_connect(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = callback.from_user.id
    sub_repo = SubscriptionRepository(session)
    sub = await sub_repo.get_active(user_id)

    if not sub or not sub.subscription_url:
        await callback.message.edit_text(
            NO_SUBSCRIPTION,
            reply_markup=connect_kb(has_subscription=False),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    text = (
        f"{SUBSCRIPTION_INFO}\n\n"
        f"🔗 <code>{sub.subscription_url}</code>\n\n"
        f"⏳ Действует до: <b>{format_date(sub.expires_at)}</b>\n"
        f"🕐 Осталось дней: <b>{days_left(sub.expires_at)}</b>\n"
        f"🟢 Статус: <b>{subscription_status(sub.expires_at)}</b>"
    )

    qr_image = generate_qr(sub.subscription_url)
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=qr_image,
        caption=text,
        reply_markup=connect_kb(has_subscription=True),
        parse_mode="HTML",
    )
    await callback.answer()
