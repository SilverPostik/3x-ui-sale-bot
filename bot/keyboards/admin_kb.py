from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text="📋 Подписки", callback_data="admin_subs")],
            [InlineKeyboardButton(text="🎁 Промокоды", callback_data="admin_promos")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="💰 Финансы", callback_data="admin_finance")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")],
        ]
    )


def admin_users_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Все пользователи", callback_data="admin_users_list")],
            [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_users_search")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_users_stats")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")],
        ]
    )


def admin_promos_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promo_create")],
            [InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin_promo_list")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")],
        ]
    )


def admin_broadcast_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Всем пользователям", callback_data="admin_broadcast_all")],
            [InlineKeyboardButton(text="✅ Активным пользователям", callback_data="admin_broadcast_active")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")],
        ]
    )


def admin_settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Цены тарифов", callback_data="admin_set_prices")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu")],
        ]
    )


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="admin_menu")]
        ]
    )


def admin_user_card_kb(user_id: int, has_sub: bool, is_active: bool) -> InlineKeyboardMarkup:
    """Карточка пользователя в админке — управление подпиской."""
    rows = [
        [
            InlineKeyboardButton(text="➕7 дней", callback_data=f"adm_sub_adj_{user_id}_7"),
            InlineKeyboardButton(text="➕30 дней", callback_data=f"adm_sub_adj_{user_id}_30"),
        ],
    ]
    if has_sub:
        rows.append([
            InlineKeyboardButton(text="➖7 дней", callback_data=f"adm_sub_adj_{user_id}_-7"),
            InlineKeyboardButton(text="➖30 дней", callback_data=f"adm_sub_adj_{user_id}_-30"),
        ])
    rows.append([InlineKeyboardButton(text="✏️ На своё число дней", callback_data=f"adm_sub_custom_{user_id}")])
    rows.append([InlineKeyboardButton(text="📅 Указать точную дату", callback_data=f"adm_sub_setdate_{user_id}")])
    if has_sub:
        toggle_text = "🔴 Отключить" if is_active else "🟢 Включить"
        rows.append([InlineKeyboardButton(text=toggle_text, callback_data=f"adm_sub_toggle_{user_id}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users_search")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
