import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import (
    UserRepository, SubscriptionRepository,
    PaymentRepository, PromocodeRepository, SettingsRepository,
)
from bot.keyboards.admin_kb import (
    admin_menu_kb, admin_users_kb, admin_promos_kb,
    admin_broadcast_kb, admin_settings_kb, admin_back_kb,
)
from config.settings import settings
from config.texts import ADMIN_PANEL, ADMIN_NO_ACCESS

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


class AdminStates(StatesGroup):
    broadcast_message = State()
    broadcast_target = State()
    create_promo_code = State()
    create_promo_type = State()
    create_promo_value = State()
    set_price_months = State()
    set_price_value = State()
    search_user = State()


# --- /admin command ---

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(ADMIN_NO_ACCESS)
        return
    await message.answer(ADMIN_PANEL, reply_markup=admin_menu_kb(), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer(ADMIN_NO_ACCESS, show_alert=True)
        return
    await callback.message.edit_text(ADMIN_PANEL, reply_markup=admin_menu_kb(), parse_mode="HTML")
    await callback.answer()


# --- Users ---

@router.callback_query(lambda c: c.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("👥 <b>Пользователи</b>", reply_markup=admin_users_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_users_list")
async def cb_admin_users_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return
    repo = UserRepository(session)
    users = await repo.get_all()
    lines = [f"👥 <b>Все пользователи ({len(users)})</b>\n"]
    for u in users[:20]:
        lines.append(f"• <code>{u.id}</code> @{u.username or '—'} {u.full_name or ''}")
    if len(users) > 20:
        lines.append(f"\n... и ещё {len(users) - 20}")
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_users_stats")
async def cb_admin_users_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return
    user_repo = UserRepository(session)
    sub_repo = SubscriptionRepository(session)
    total = await user_repo.count()
    active = await sub_repo.count_active()
    text = (
        f"📊 <b>Статистика пользователей</b>\n\n"
        f"👥 Всего пользователей: <b>{total}</b>\n"
        f"✅ Активных подписок: <b>{active}</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_users_search")
async def cb_admin_users_search(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🔍 Введите Telegram ID пользователя:", reply_markup=admin_back_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.search_user)
    await callback.answer()


@router.message(AdminStates.search_user)
async def handle_search_user(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный ID.", reply_markup=admin_back_kb())
        return
    repo = UserRepository(session)
    user = await repo.get_by_id(uid)
    sub_repo = SubscriptionRepository(session)
    sub = await sub_repo.get_active(uid)
    if not user:
        await message.answer("❌ Пользователь не найден.", reply_markup=admin_back_kb(), parse_mode="HTML")
        return
    text = (
        f"👤 <b>Пользователь</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Username: @{user.username or '—'}\n"
        f"Имя: {user.full_name or '—'}\n"
        f"Подписка: {'✅ Активна' if sub else '❌ Нет'}\n"
    )
    if sub:
        from bot.utils.formatters import format_date, days_left
        text += f"Истекает: {format_date(sub.expires_at)} ({days_left(sub.expires_at)} дн.)"
    await message.answer(text, reply_markup=admin_back_kb(), parse_mode="HTML")


# --- Subscriptions ---

@router.callback_query(lambda c: c.data == "admin_subs")
async def cb_admin_subs(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return
    sub_repo = SubscriptionRepository(session)
    active = await sub_repo.count_active()
    expired = await sub_repo.get_expired()
    text = (
        f"📋 <b>Подписки</b>\n\n"
        f"✅ Активных: <b>{active}</b>\n"
        f"❌ Истекших (не деактивированных): <b>{len(expired)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


# --- Promocodes ---

@router.callback_query(lambda c: c.data == "admin_promos")
async def cb_admin_promos(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🎁 <b>Промокоды</b>", reply_markup=admin_promos_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_promo_list")
async def cb_admin_promo_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return
    repo = PromocodeRepository(session)
    promos = await repo.get_all()
    if not promos:
        await callback.message.edit_text("🎁 Промокодов нет.", reply_markup=admin_back_kb(), parse_mode="HTML")
        await callback.answer()
        return
    lines = [f"🎁 <b>Промокоды ({len(promos)})</b>\n"]
    for p in promos:
        status = "✅" if p.is_active else "❌"
        lines.append(
            f"{status} <code>{p.code}</code> — {p.type}: {p.value} "
            f"({p.activations_count}/{p.max_activations or '∞'} акт.)"
        )
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_promo_create")
async def cb_admin_promo_create(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🎁 Введите промокод в формате:\n"
        "<code>КОД ТИП ЗНАЧЕНИЕ [МАКС_АКТИВАЦИЙ] [ОДНОРАЗОВЫЙ]</code>\n\n"
        "Тип: <b>days</b> или <b>discount</b>\n"
        "Пример: <code>PROMO2025 days 30 100 0</code>\n"
        "Пример: <code>SALE50 discount 50 50 1</code>",
        reply_markup=admin_back_kb(),
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.create_promo_code)
    await callback.answer()


@router.message(AdminStates.create_promo_code)
async def handle_create_promo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer("❌ Неверный формат.", reply_markup=admin_back_kb())
        return
    code = parts[0]
    type_ = parts[1]
    try:
        value = int(parts[2])
        max_act = int(parts[3]) if len(parts) > 3 else None
        one_time = bool(int(parts[4])) if len(parts) > 4 else False
    except (ValueError, IndexError):
        await message.answer("❌ Ошибка в значениях.", reply_markup=admin_back_kb())
        return
    repo = PromocodeRepository(session)
    promo = await repo.create(code=code, type=type_, value=value, max_activations=max_act, is_one_time=one_time)
    await message.answer(f"✅ Промокод <code>{promo.code}</code> создан!", reply_markup=admin_back_kb(), parse_mode="HTML")


# --- Broadcast ---

@router.callback_query(lambda c: c.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("📢 <b>Рассылка</b>", reply_markup=admin_broadcast_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data in ("admin_broadcast_all", "admin_broadcast_active"))
async def cb_admin_broadcast_target(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await state.update_data(broadcast_target=callback.data)
    await callback.message.edit_text("✏️ Введите текст рассылки:", reply_markup=admin_back_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.broadcast_message)
    await callback.answer()


@router.message(AdminStates.broadcast_message)
async def handle_broadcast(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    await state.clear()
    target = data.get("broadcast_target", "admin_broadcast_all")
    text = message.text or ""

    user_repo = UserRepository(session)
    sub_repo = SubscriptionRepository(session)

    if target == "admin_broadcast_active":
        active_subs = await sub_repo.get_expiring_soon(days=99999)  # all active
        user_ids = list({s.user_id for s in active_subs})
    else:
        users = await user_repo.get_all()
        user_ids = [u.id for u in users]

    sent = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            pass

    await message.answer(f"✅ Рассылка завершена. Отправлено: <b>{sent}</b>", reply_markup=admin_back_kb(), parse_mode="HTML")


# --- Finance ---

@router.callback_query(lambda c: c.data == "admin_finance")
async def cb_admin_finance(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return
    payment_repo = PaymentRepository(session)
    today = await payment_repo.revenue_today()
    month = await payment_repo.revenue_month()
    total = await payment_repo.sum_revenue()
    text = (
        f"💰 <b>Финансы</b>\n\n"
        f"Сегодня: <b>{today} ⭐</b>\n"
        f"Месяц: <b>{month} ⭐</b>\n"
        f"Всего: <b>{total} ⭐</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


# --- Settings ---

@router.callback_query(lambda c: c.data == "admin_settings")
async def cb_admin_settings(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("⚙️ <b>Настройки</b>", reply_markup=admin_settings_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_set_prices")
async def cb_admin_set_prices(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "💰 Введите цены в формате:\n<code>1:100 3:250 6:450 12:800</code>",
        reply_markup=admin_back_kb(),
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.set_price_value)
    await callback.answer()


@router.message(AdminStates.set_price_value)
async def handle_set_prices(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    repo = SettingsRepository(session)
    parts = message.text.strip().split()
    updated = []
    for part in parts:
        try:
            months_str, price_str = part.split(":")
            months = int(months_str)
            price = int(price_str)
            await repo.set(f"price_{months}", str(price))
            updated.append(f"{months} мес. = {price} ⭐")
        except Exception:
            pass
    if updated:
        await message.answer("✅ Цены обновлены:\n" + "\n".join(updated), reply_markup=admin_back_kb(), parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка формата.", reply_markup=admin_back_kb())
