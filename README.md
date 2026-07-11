# Продажник — VPN Telegram Bot

Production-ready Telegram бот для продажи VPN-подписок через панель **3x-ui**.  
Протокол: **VLESS + Reality**. Оплата: **Telegram Stars**, **СБП**, **банковские карты** и **криптовалюта** (Platega).

---

## Стек

| Компонент | Технология |
|---|---|
| Язык | Python 3.12+ |
| Telegram | aiogram 3.x |
| База данных | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x async |
| Миграции | Alembic |
| Планировщик | APScheduler |
| Деплой | Docker + Docker Compose |

---

## Быстрый старт

### 1. Клонирование

```bash
git clone https://github.com/SilverPostik/3x-ui-sale-bot.git
cd 3x-ui-sale-bot
cp .env.example .env
nano .env
```

### 2. Переменные окружения

```env
# Бот
BOT_TOKEN=токен_от_BotFather

# PostgreSQL
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=vpnbot
POSTGRES_USER=vpnbot
POSTGRES_PASSWORD=сильный_пароль

# 3x-ui
THREEXUI_URL=https://ip:порт/путь/
THREEXUI_USERNAME=логин
THREEXUI_PASSWORD=пароль
THREEXUI_SUB_PORT=2096
REALITY_INBOUND_ID=1
DEFAULT_LIMIT_IP=1

# Telegram Stars (токен не нужен, оставить пустым)
TELEGRAM_STARS_PROVIDER_TOKEN=

# Platega.io — СБП, банковские карты, криптовалюта (необязательно)
ENABLE_PLATEGA=false
PLATEGA_MERCHANT_ID=id_из_ЛК_Platega
PLATEGA_SECRET=секрет_из_ЛК_Platega
PLATEGA_METHOD_SBP=2
PLATEGA_METHOD_CARD=1
PLATEGA_METHOD_CRYPTO=13
WEBHOOK_HOST=https://pay.твойдомен.ru

# Администраторы (через запятую, без скобок)
ADMIN_IDS=123456789,987654321

# Поддержка
SUPPORT_USERNAME=username_без_собачки

# Уведомления об истечении
NOTIFY_7_DAYS=true
NOTIFY_3_DAYS=true
NOTIFY_1_DAY=true
DISABLE_EXPIRED_USERS=true
```

### 3. Запуск

```bash
docker compose up -d --build
```

Миграции применяются автоматически при старте.

---

## Настройка Platega (webhook)

Platega принимает callback **только по HTTPS с валидным сертификатом** (в отличие
от ЮMoney, HTTP не подойдёт). Порты 443 и 8443 у тебя уже заняты VLESS-инбаундами
3x-ui, поэтому HTTPS для вебхука вешаем на отдельный порт (по умолчанию `9443`).

```bash
chmod +x setup_webhook.sh
sudo ./setup_webhook.sh pay.твойдомен.ru email@mail.ru
docker compose up -d --build
```

Скрипт автоматически:
- проверит что домен указывает на сервер
- выпустит сертификат Let's Encrypt (через `certbot certonly --webroot`, не трогая порты 443/8443)
- настроит nginx: `:9443 (SSL) /platega/notify` → бот на `127.0.0.1:8080`
- откроет порт 9443 в ufw
- настроит автообновление сертификата (cron, ежедневно в 03:00)
- обновит `WEBHOOK_HOST` в `.env`
- перезапустит бота

Свой порт можно задать третьим аргументом: `sudo ./setup_webhook.sh pay.домен.ru email 9443`
(главное — не 443 и не 8443, они заняты VPN).

После этого в личном кабинете Platega (Настройки → Callback URLs) укажи:
```
https://pay.твойдомен.ru:9443/platega/notify
```

Там же в личном кабинете уточни `PLATEGA_MERCHANT_ID`, `PLATEGA_SECRET` и точный код
способа оплаты для карточного эквайринга (`PLATEGA_METHOD_CARD`) — эти данные
индивидуальны для каждого мерчанта.

> В Cloudflare A-запись должна быть с **серой тучкой** (Proxy: OFF) — иначе
> сертификат Let's Encrypt не выпустится и HTTPS-запросы Platega не дойдут до сервера.



---

## Структура проекта

```
├── bot/
│   ├── handlers/       # Обработчики: start, payment, profile, connect...
│   ├── keyboards/      # Inline-клавиатуры
│   ├── middlewares/    # DB-сессия, авторегистрация пользователей
│   ├── repositories/   # Слой БД (Repository Pattern)
│   ├── services/       # Бизнес-логика: платежи, подписки, 3x-ui, Platega
│   └── webhook/        # aiohttp-обработчик Platega callback
├── admin/              # Панель администратора
├── scheduler/          # Ежедневные задачи (уведомления, отключение)
├── database/
│   └── models/         # SQLAlchemy модели
├── config/
│   ├── settings.py     # Pydantic Settings
│   └── texts.py        # Все тексты бота
├── migrations/         # Alembic миграции
├── main.py             # Точка входа
├── setup_webhook.sh    # Скрипт настройки SSL
├── docker-compose.yml
└── .env.example
```

---

## Функционал

### Пользователь
- `/start` — главное меню
- **Личный кабинет** — тариф, статус, дата окончания
- **Подключиться** — Subscription URL + QR-код
- **Инструкция** — HAPP для Android / iOS / Windows / macOS
- **Купить VPN** — тарифы 1/3/6/12 месяцев
- **Оплата** — Telegram Stars или Platega (СБП / карта / криптовалюта)
- **Промокод** — скидка или бесплатные дни

### Администратор (`/admin`)
- Статистика пользователей и подписок
- Выручка: за день / месяц / всё время (Stars и RUB отдельно)
- Управление промокодами
- Рассылка всем или только активным
- Настройка цен тарифов
- `/backup` — дамп базы данных
- `/ping` — проверка бота
- `/xui` — проверка соединения с 3x-ui

### Автоматика
- Уведомления за 7 / 3 / 1 день до конца подписки
- Автоотключение истёкших клиентов в 3x-ui
- Запуск: каждый день в 09:00 UTC

---

## Платёжная архитектура

```
Выбор тарифа → Выбор способа оплаты
                    │
     ┌──────────────┼───────────────────────────┐
Telegram Stars     СБП / Карта / Крипта (Platega)
     │                            │
invoice_payload        POST /transaction/process
     │                       (redirect URL)
successful_payment       webhook POST /platega/notify
     │                    (либо ручная проверка через
     │                     GET /transaction/{id})
     └──────────────┬───────────────────────────┘
               PaymentService
               .confirm_payment()
                    │
           SubscriptionService
           .extend_subscription()
                    │
              3x-ui клиент создан/продлён
```

Модель `Payment` единая для всех провайдеров:

| Поле | Описание |
|---|---|
| `provider` | `telegram_stars`, `platega_sbp`, `platega_card` или `platega_crypto` |
| `currency` | `XTR` или `RUB` |
| `amount` | сумма (звёзды или рубли) |
| `external_payment_id` | charge_id (Stars) или transactionId (Platega) |
| `status` | `pending` → `paid` |

---

## Решение проблем

**Бот не запускается:**
```bash
docker compose logs bot
```

**Проблема с БД:**
```bash
docker compose logs db
docker compose down && docker compose up -d
```

**3x-ui не подключается:**  
Проверь `THREEXUI_URL` — должен включать путь (`/d7tCPj1V3X2KLzvTo6/`), и что панель доступна с VPS.

**Platega webhook не работает:**  
Проверь что домен резолвится (`dig pay.домен.ru`), сертификат есть (`ls /etc/letsencrypt/live/`), порт вебхука открыт (`ufw allow 9443`, или тот порт, что указал при запуске `setup_webhook.sh`). ⚠️ Порт 443 занят VLESS Reality в 3x-ui — под вебхук его использовать нельзя.

**`docker-compose: command not found`:**
```bash
sudo apt install docker-compose-v2 -y
```

---

## Требования к серверу

- Ubuntu 22.04+
- Docker 24+ и Docker Compose v2
- 3x-ui с настроенным VLESS Reality inbound
- Для Platega: домен с A-записью (Cloudflare Proxy OFF)

---

## Безопасность

- Секреты только в `.env`, файл добавлен в `.gitignore`
- `ADMIN_IDS` проверяются на уровне хендлеров
- Повторная обработка платежа защищена уникальным `external_payment_id`
- Сертификат монтируется в Docker read-only
