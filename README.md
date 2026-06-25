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
git clone https://github.com/SilverPostik/3x-ui-sale-bot.git
cd 3x-ui-sale-bot
cp .env.example .env
nano .env   # заполнить все переменные
```

### 2. Переменные окружения (.env)

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `POSTGRES_*` | Параметры PostgreSQL |
| `THREEXUI_URL` | URL панели 3x-ui (с портом) |
| `THREEXUI_USERNAME` | Логин 3x-ui (необязательно при использовании API токена) |
| `THREEXUI_PASSWORD` | Пароль 3x-ui (необязательно при использовании API токена) |
| `THREEXUI_API_TOKEN` | API токен 3x-ui (Bearer) |
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

## Решение проблем

### Ошибка: `Cannot install aiohttp==3.10.5`

Если при установке вы видите конфликт между `aiogram` и `aiohttp`:
```
The conflict is caused by:
    The user requested aiohttp==3.10.5
    aiogram 3.10.0 depends on aiohttp~=3.9.0
```

**Решение:** Версия `aiohttp` уже исправлена на `3.9.5` в `requirements.txt`. Пересоберите контейнер:

```bash
docker-compose build --no-cache
docker-compose up -d
```

### Ошибка: `docker-compose: command not found`

Установите Docker Compose v2:

```bash
sudo apt install docker-compose-v2 -y
```

Или установите через Docker Desktop на вашем компьютере.

### Ошибка при подключении к БД

1. Убедитесь, что `.env` заполнен правильно
2. Проверьте статус БД: `docker-compose logs db`
3. Пересоздайте контейнеры: `docker-compose down && docker-compose up -d`

---

## Безопасность

- Все секреты только в `.env` — не коммитить в git
- Добавьте `.env` в `.gitignore`
- ADMIN_IDS проверяется на уровне обработчиков
- Повторная обработка платежа защищена уникальным `telegram_payment_charge_id`
