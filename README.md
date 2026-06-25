# VPN Telegram Bot

Production-ready Telegram бот для продажи VPN-доступа на базе панели **3x-ui**.  
Протокол: **VLESS + Reality**. Клиент: **HAPP VPN**. Оплата: **Telegram Stars**.

---

## Стек технологий

| Компонент | Технология |
|---|---|
| Язык | Python 3.12+ |
| Telegram | aiogram 3.x |
| База данных | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x (async) |
| Миграции | Alembic |
| Конфиг | Pydantic Settings |
| Планировщик | APScheduler |
| Деплой | Docker + Docker Compose |

---

## Быстрый старт

### 1. Клонирование и настройка окружения

```bash
git clone <repo>
cd vpn_bot
cp .env.example .env
nano .env   # заполнить все переменные
```

### 2. Переменные окружения (.env)

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `POSTGRES_*` | Параметры PostgreSQL |
| `THREEXUI_URL` | URL панели 3x-ui (с портом) |
| `THREEXUI_USERNAME` | Логин 3x-ui |
| `THREEXUI_PASSWORD` | Пароль 3x-ui |
| `REALITY_INBOUND_ID` | ID inbound VLESS Reality в 3x-ui |
| `TELEGRAM_STARS_PROVIDER_TOKEN` | Токен провайдера Stars (из @BotFather) |
| `ADMIN_IDS` | Telegram ID администраторов через запятую |
| `SUPPORT_USERNAME` | Username поддержки (без @) |
| `NOTIFY_7_DAYS` | Уведомление за 7 дней (true/false) |
| `NOTIFY_3_DAYS` | Уведомление за 3 дня (true/false) |
| `NOTIFY_1_DAY` | Уведомление за 1 день (true/false) |
| `DISABLE_EXPIRED_USERS` | Отключать истёкших пользователей (true/false) |

### 3. Запуск через Docker Compose

```bash
docker compose up -d --build
```

Миграции применяются автоматически при старте бота.

### 4. Запуск без Docker (для разработки)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Применить миграции
alembic -c migrations/alembic.ini upgrade head

# Запустить бота
python main.py
```

---

## Структура проекта

```
vpn_bot/
│
├── bot/
│   ├── handlers/          # Обработчики команд и callback'ов
│   ├── keyboards/         # Inline-клавиатуры
│   ├── middlewares/       # DB-сессия, авто-регистрация пользователей
│   ├── repositories/      # Слой доступа к БД (Repository Pattern)
│   ├── services/          # Бизнес-логика (3x-ui, подписки, платежи)
│   └── utils/             # Хелперы: QR, форматирование дат
│
├── admin/                 # Панель администратора (/admin)
├── scheduler/             # APScheduler: ежедневная проверка подписок
├── database/
│   └── models/            # SQLAlchemy ORM-модели
├── config/
│   ├── settings.py        # Pydantic Settings (.env)
│   └── texts.py           # Все тексты бота в одном месте
├── migrations/            # Alembic миграции
│
├── main.py                # Точка входа
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Функционал

### Пользователь
- `/start` — главное меню
- **Личный кабинет** — тариф, дата окончания, статус
- **Подключиться** — Subscription URL + QR-код
- **Инструкция** — HAPP для Android / iOS / Windows / macOS
- **Поддержка** — контакт поддержки
- **Промокод** — скидка или дополнительные дни
- **Купить VPN** — тарифы 1/3/6/12 месяцев, оплата Telegram Stars

### Администратор (`/admin`)
- Список и поиск пользователей
- Статистика подписок
- Управление промокодами (создание, список)
- Рассылка (всем / активным)
- Финансы: выручка за день / месяц / всё время
- Настройка цен тарифов

### Автоматика
- Уведомления за 7 / 3 / 1 день до окончания подписки
- Автоматическое отключение истёкших пользователей в 3x-ui
- Задача запускается ежедневно в 09:00 UTC

---

## Добавление нового типа VPN (расширение)

1. В `bot/services/xui_client.py` добавить методы для нового inbound.
2. В `.env` добавить `NEW_INBOUND_ID`.
3. В `bot/services/subscription_service.py` добавить ветку `inbound_type`.
4. В `database/models/subscription.py` поле `inbound_type` уже готово.

Никакой переработки архитектуры не требуется.

---

## Требования к серверу

- Ubuntu 22.04+
- Docker 24+ и Docker Compose v2
- Панель 3x-ui с настроенным inbound VLESS Reality
- Telegram-бот с включёнными платежами Stars (@BotFather → Payments)

---

## Безопасность

- Все секреты только в `.env` — не коммитить в git
- Добавьте `.env` в `.gitignore`
- ADMIN_IDS проверяется на уровне обработчиков
- Повторная обработка платежа защищена уникальным `telegram_payment_charge_id`

---

## Диагностика 3x-ui (ВАЖНО прочитать)

### Команды для администратора

| Команда | Описание |
|---|---|
| `/ping` | Проверить соединение с 3x-ui, найти inbound по REALITY_INBOUND_ID |
| `/xui` | Показать все inbound'ы с их ID |
| `/admin` | Панель управления |
| `/backup` | Скачать дамп PostgreSQL |

### Почему запросы не доходят до панели

Наиболее частые причины:

1. **Неверный URL** — `THREEXUI_URL` должен включать порт и НЕ иметь слэш в конце.
   Правильно: `https://1.2.3.4:2053` или `https://example.com:2053`

2. **Нестандартный web_base_path** — если в настройках 3x-ui задан "Web Base Path" (например `/secret/`), добавь его в URL:
   `THREEXUI_URL=https://1.2.3.4:2053/secret`

3. **Самоподписанный сертификат** — клиент работает с `ssl=False`, это нормально.

4. **Неверный REALITY_INBOUND_ID** — узнать ID: запусти `/xui` в боте после старта.

5. **Пустые ответы от API** — известный баг в 3x-ui v2.6.x (issue #3052, #3236).
   Клиент делает 3 попытки с задержкой 1 сек автоматически.

6. **subId не генерируется** — 3x-ui не создаёт subId при API-вызове (issue #3237).
   Бот передаёт subId явно — это единственный правильный способ.

### Ручная проверка API с сервера

```bash
# Логин
curl -X POST http://localhost:2053/login \
  -d "username=admin&password=yourpassword"

# Список inbound'ов (нужна session cookie)
curl -b "session=<cookie>" http://localhost:2053/panel/api/inbounds/list
```

---

## Переменные .env (полный список)

```env
BOT_TOKEN=                      # от @BotFather
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=vpnbot
POSTGRES_USER=vpnbot
POSTGRES_PASSWORD=

THREEXUI_URL=https://1.2.3.4:2053    # БЕЗ слэша в конце
THREEXUI_USERNAME=admin
THREEXUI_PASSWORD=
REALITY_INBOUND_ID=1                  # ID inbound в панели (узнать через /xui)
DEFAULT_LIMIT_IP=1                    # Устройств на подписку

TELEGRAM_STARS_PROVIDER_TOKEN=        # из @BotFather → Payments

ADMIN_IDS=123456789                   # через запятую

SUPPORT_USERNAME=your_support

NOTIFY_7_DAYS=true
NOTIFY_3_DAYS=true
NOTIFY_1_DAY=true
DISABLE_EXPIRED_USERS=true

# ЮMoney (опционально)
ENABLE_YOOMONEY=false
YOOMONEY_WALLET=4100118XXXXXXXXX
YOOMONEY_SECRET=
WEBHOOK_HOST=https://yourdomain.com
```
