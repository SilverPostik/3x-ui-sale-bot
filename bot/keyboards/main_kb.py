from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import settings


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📁 Личный кабинет", callback_data="profile"),
                InlineKeyboardButton(text="🔐 Подключиться", callback_data="connect"),
            ],
            [
                InlineKeyboardButton(text="📚 Инструкция", callback_data="instruction"),
                InlineKeyboardButton(text="📖 Поддержка", callback_data="support"),
            ],
            [InlineKeyboardButton(text="🎁 Активировать промокод", callback_data="promo")],
            [InlineKeyboardButton(text="🚀 Купить VPN", callback_data="buy_choose")],
        ]
    )


def payment_method_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="buy")],
    ]
    if settings.ENABLE_YOOMONEY:
        buttons.append([InlineKeyboardButton(text="💳 ЮMoney (карта/кошелёк)", callback_data="buy_yoomoney")])
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="buy_choose")],
            [InlineKeyboardButton(text="🔗 Моя подписка", callback_data="connect")],
            [InlineKeyboardButton(text="💳 История платежей", callback_data="payment_history")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def connect_kb(has_subscription: bool) -> InlineKeyboardMarkup:
    if not has_subscription:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Купить VPN", callback_data="buy_choose")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить данные", callback_data="connect")],
            [InlineKeyboardButton(text="📚 Открыть инструкцию", callback_data="instruction")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def instruction_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 Android", callback_data="instr_android"),
                InlineKeyboardButton(text="🍎 iPhone", callback_data="instr_ios"),
            ],
            [
                InlineKeyboardButton(text="💻 Windows", callback_data="instr_windows"),
                InlineKeyboardButton(text="🍏 macOS", callback_data="instr_macos"),
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def plans_kb(prices: dict[int, int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"1 месяц — {prices[1]} ⭐", callback_data="plan_1")],
            [InlineKeyboardButton(text=f"3 месяца — {prices[3]} ⭐", callback_data="plan_3")],
            [InlineKeyboardButton(text=f"6 месяцев — {prices[6]} ⭐", callback_data="plan_6")],
            [InlineKeyboardButton(text=f"12 месяцев — {prices[12]} ⭐", callback_data="plan_12")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
    )
