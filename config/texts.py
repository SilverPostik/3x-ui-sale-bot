"""
All bot text messages. Edit freely without touching handler code.
"""

WELCOME = (
    "👋 <b>Добро пожаловать в VPN-сервис!</b>\n\n"
    "🔐 Быстрый, безопасный и надёжный VPN на базе VLESS Reality.\n"
    "📱 Поддерживаем Android, iOS, Windows и macOS через приложение <b>HAPP</b>.\n\n"
    "Выберите действие:"
)

NO_SUBSCRIPTION = (
    "❌ У вас нет активной подписки.\n\n"
    "Нажмите <b>🚀 Купить VPN</b>, чтобы начать."
)

SUBSCRIPTION_INFO = (
    "🔐 <b>Ваша подписка</b>\n\n"
    "📋 Subscription URL скопирован ниже.\n"
    "Также вы можете отсканировать QR-код приложением HAPP."
)

PROFILE_TEMPLATE = (
    "👤 <b>Личный кабинет</b>\n\n"
    "🆔 Telegram ID: <code>{telegram_id}</code>\n"
    "📅 Дата регистрации: {registered_at}\n"
    "📦 Тариф: {plan}\n"
    "⏳ Действует до: {expires_at}\n"
    "🕐 Осталось дней: {days_left}\n"
    "🟢 Статус: {status}\n"
    "📱 Устройств: {devices}"
)

PLAN_NAMES = {
    1: "1 месяц",
    3: "3 месяца",
    6: "6 месяцев",
    12: "12 месяцев",
}

CHOOSE_PLAN = "🚀 <b>Выберите тариф:</b>"

PAYMENT_INVOICE_TITLE = "VPN подписка — {plan}"
PAYMENT_INVOICE_DESCRIPTION = (
    "Доступ к VPN на {plan}. Протокол VLESS Reality. Неограниченный трафик."
)

PAYMENT_SUCCESS = (
    "✅ <b>Оплата прошла успешно!</b>\n\n"
    "Ваша подписка активирована.\n"
    "Используйте кнопку <b>🔐 Подключиться</b> для получения ссылки."
)

PROMO_ENTER = "🎁 Введите промокод:"
PROMO_INVALID = "❌ Промокод недействителен или уже использован."
PROMO_EXPIRED = "❌ Срок действия промокода истёк."
PROMO_LIMIT = "❌ Промокод исчерпал лимит активаций."
PROMO_ALREADY_USED = "❌ Вы уже использовали этот промокод."
PROMO_SUCCESS_DAYS = "✅ Промокод активирован! Добавлено дней: <b>{days}</b>."
PROMO_SUCCESS_DISCOUNT = "✅ Промокод активирован! Скидка <b>{discount}%</b> применена к следующей покупке."

NOTIFY_7_DAYS = (
    "⏰ <b>Подписка заканчивается через 7 дней</b>\n\n"
    "Продлите подписку заранее, чтобы не прерывать доступ."
)
NOTIFY_3_DAYS = (
    "⚠️ <b>Подписка заканчивается через 3 дня</b>\n\n"
    "Не забудьте продлить подписку!"
)
NOTIFY_1_DAY = (
    "🚨 <b>Подписка заканчивается завтра!</b>\n\n"
    "Срочно продлите подписку, чтобы не потерять доступ."
)
NOTIFY_EXPIRED = (
    "❌ <b>Ваша подписка истекла</b>\n\n"
    "Для возобновления доступа — оформите новую подписку."
)

SUPPORT_TEXT = "📞 <b>Поддержка</b>\n\nОбратитесь к нашему оператору: @{username}"

INSTRUCTION_CHOOSE_PLATFORM = "📚 Выберите вашу платформу:"

INSTRUCTIONS = {
    "android": (
        "📱 <b>Инструкция для Android</b>\n\n"
        "1. Установите приложение <b>HAPP VPN</b> из Google Play:\n"
        "   https://play.google.com/store/apps/details?id=com.happ.vpn\n\n"
        "2. Откройте приложение → нажмите <b>+</b> → <b>Import from URL</b>.\n\n"
        "3. Вставьте ваш <b>Subscription URL</b> из раздела «Подключиться».\n\n"
        "4. Нажмите <b>Update</b> для загрузки серверов.\n\n"
        "5. Выберите сервер и нажмите <b>Connect</b>.\n\n"
        "✅ Готово! VPN активен."
    ),
    "ios": (
        "🍎 <b>Инструкция для iPhone (iOS)</b>\n\n"
        "1. Установите <b>HAPP VPN</b> из App Store:\n"
        "   https://apps.apple.com/app/happ-proxy-utility/id6504287215\n\n"
        "2. Откройте приложение → нажмите <b>+</b> → <b>Import from URL</b>.\n\n"
        "3. Вставьте ваш <b>Subscription URL</b> из раздела «Подключиться».\n\n"
        "4. Нажмите <b>Update Subscription</b>.\n\n"
        "5. Выберите сервер → нажмите <b>Connect</b>.\n\n"
        "✅ Готово! VPN активен."
    ),
    "windows": (
        "💻 <b>Инструкция для Windows</b>\n\n"
        "1. Скачайте <b>HAPP VPN</b> для Windows:\n"
        "   https://github.com/happ-client/happ-desktop/releases\n\n"
        "2. Запустите установщик, откройте приложение.\n\n"
        "3. Нажмите <b>Subscription</b> → <b>Add</b>.\n\n"
        "4. Вставьте ваш <b>Subscription URL</b>.\n\n"
        "5. Нажмите <b>Update</b> → выберите сервер → <b>Connect</b>.\n\n"
        "✅ Готово! VPN активен."
    ),
    "macos": (
        "🍏 <b>Инструкция для macOS</b>\n\n"
        "1. Скачайте <b>HAPP VPN</b> для macOS:\n"
        "   https://github.com/happ-client/happ-desktop/releases\n\n"
        "2. Перетащите приложение в папку Applications.\n\n"
        "3. Откройте HAPP → <b>Subscription</b> → <b>Add</b>.\n\n"
        "4. Вставьте ваш <b>Subscription URL</b>.\n\n"
        "5. Нажмите <b>Update</b> → выберите сервер → <b>Connect</b>.\n\n"
        "✅ Готово! VPN активен."
    ),
}

ADMIN_PANEL = "⚙️ <b>Панель администратора</b>"
ADMIN_NO_ACCESS = "❌ Доступ запрещён."

ERROR_GENERIC = "❌ Произошла ошибка. Попробуйте позже."
