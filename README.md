# Продажник — Telegram-бот для аренды виртуальных серверов

Production-ready Telegram бот для продажи доступа к виртуальному серверу через панель **3x-ui**.
Протокол: **VLESS + Reality**. Оплата: **Telegram Stars** и **ЮMoney** (легко расширяется другими провайдерами — СБП, карты РФ, криптоплатежи).

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

# ID инбаундов 3x-ui, куда выдаётся клиент. Можно несколько через запятую —
# один и тот же клиент (UUID + subId) будет одновременно выдан во все
# перечисленные инбаунды, subscription-ссылка подхватит их автоматически.
# Пример: основной Reality-инбаунд + резервный WS+TLS для нестабильных сетей.
INBOUND_IDS=1,2
DEFAULT_LIMIT_IP=1

# Telegram Stars (токен не нужен, оставить пустым)
TELEGRAM_STARS_PROVIDER_TOKEN=

# ЮMoney (необязательно)
ENABLE_YOOMONEY=false
YOOMONEY_WALLET=номер_кошелька
YOOMONEY_SECRET=секрет_уведомлений
WEBHOOK_HOST=https://pay.твойдомен.ru

# Администраторы (через запятую, без скобок)
ADMIN_IDS=123456789,987654321

# Поддержка (username и/или e-mail — формат группы банк не принимает)
SUPPORT_USERNAME=username_без_собачки
SUPPORT_EMAIL=support@твойдомен.ru

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

## Настройка ЮMoney (webhook)

ЮMoney требует HTTPS с валидным сертификатом. Запусти скрипт один раз на VPS:

```bash
chmod +x setup_webhook.sh
sudo ./setup_webhook.sh pay.твойдомен.ru email@mail.ru
docker compose up -d --build
```

Скрипт автоматически:
- проверит что домен указывает на сервер
- установит certbot и выпустит SSL-сертификат
- обновит `WEBHOOK_HOST` в `.env`
- добавит автообновление сертификата в cron

После этого в [настройках ЮMoney](https://yoomoney.ru/transfer/myservices/http-notification) укажи:
```
https://pay.твойдомен.ru/yoomoney/notify
```

> В Cloudflare A-запись должна быть с **серой тучкой** (Proxy: OFF).

Если банк/платёжный агрегатор подключает приём по СБП, картам РФ или
криптовалюте — новый провайдер добавляется по тому же паттерну, что и
`yoomoney_client.py` / `yoomoney_payment.py`: свой клиент API + свой обработчик
вебхука + добавление ветки в `PaymentService`.

---

## Юридические документы и требования банка/платёжного провайдера

Для подключения приёма платежей (СБП, карты РФ, крипто и т.д.) провайдеры
обычно требуют, чтобы в боте были **постоянно доступны**:

- политика конфиденциальности;
- пользовательское соглашение;
- контакты поддержки (username/e-mail/тикет-система — **не** формат группы);
- прозрачные тарифы с указанием, сколько и за что платит клиент.

Всё это уже реализовано:

- Тексты документов лежат в `config/legal.py` — отредактируйте под свою
  компанию (укажите реальное наименование сервиса/оператора). **Не указывайте
  ИНН и другие реквизиты**, если верификация по ним не проводится.
- Кнопка **📄 Документы и тарифы** в главном меню открывает подменю:
  Тарифы / Политика конфиденциальности / Пользовательское соглашение / Поддержка.
  Реализовано в `bot/handlers/legal.py`.
- Тарифы формируются динамически из текущих цен в БД (`SettingsRepository`),
  так что при изменении цен через админ-панель раздел «Тарифы» обновляется
  автоматически.

Если ваш проект связан с обходом блокировок, DPI/ТСПУ, глушением сигналов
или иной тематикой, ограниченной законодательством РФ, — такие упоминания
нужно убрать из бота и канала/сайта проекта. В этом репозитории сервис
позиционируется нейтрально как «аренда виртуального сервера» и подобных
упоминаний не содержит.

---

## Структура проекта

```
├── bot/
│   ├── handlers/       # Обработчики: start, payment, profile, connect, legal...
│   ├── keyboards/      # Inline-клавиатуры
│   ├── middlewares/    # DB-сессия, авторегистрация пользователей
│   ├── repositories/   # Слой БД (Repository Pattern)
│   ├── services/       # Бизнес-логика: платежи, подписки, 3x-ui, ЮMoney
│   └── webhook/        # aiohttp-обработчик ЮMoney уведомлений
├── admin/              # Панель администратора
├── scheduler/          # Ежедневные задачи (уведомления, отключение)
├── database/
│   └── models/         # SQLAlchemy модели
├── config/
│   ├── settings.py     # Pydantic Settings
│   ├── texts.py        # Все тексты бота
│   └── legal.py         # Политика конфиденциальности, соглашение, тарифы
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
- **Инструкция** — приложение HAPP для Android / iOS / Windows / macOS
- **Купить сервер** — тарифы 1/3/6/12 месяцев
- **Оплата** — Telegram Stars или ЮMoney (карта/кошелёк)
- **Промокод** — скидка или бесплатные дни
- **Документы и тарифы** — политика конфиденциальности, пользовательское
  соглашение, актуальные тарифы, поддержка

### Администратор (`/admin`)
- Статистика пользователей и подписок
- Выручка: за день / месяц / всё время (Stars и RUB отдельно)
- Управление промокодами
- Рассылка всем или только активным
- Настройка цен тарифов
- `/backup` — дамп базы данных
- `/ping` — проверка бота и всех настроенных inbound'ов 3x-ui
- `/xui` — список inbound'ов на панели

### Автоматика
- Уведомления за 7 / 3 / 1 день до конца подписки
- Автоотключение истёкших клиентов в 3x-ui (по всем inbound'ам клиента)
- Запуск: каждый день в 09:00 UTC

---

## Множественные inbound'ы

Один клиент может быть выдан сразу в несколько inbound'ов панели 3x-ui —
например, основной VLESS Reality (порт 443) и резервный VLESS WS+TLS
(порт 8443) для случаев, когда прямое соединение по Reality недоступно.

Настраивается одной переменной:

```env
INBOUND_IDS=1,2
```

Как это работает:
- `xui_client.add_client()` создаёт клиента с одним UUID и одним `subId`,
  но сразу привязывает его ко всем ID из `INBOUND_IDS` (`inboundIds` в
  запросе к API 3x-ui принимает список).
- Subscription-ссылка (`/sub/<subId>`) в 3x-ui агрегирует конфиги клиента
  из всех inbound'ов, где он существует — пользователь получает все
  варианты подключения по одной ссылке/QR-коду автоматически.
- Продление и отключение подписки (`update_client` / `disable_client`)
  тоже применяются ко всем inbound'ам клиента.
- ID inbound'ов, выданных конкретной подписке, сохраняются в колонке
  `xui_inbound_ids` таблицы `subscriptions` (миграция `0004`).

---

## Платёжная архитектура

```
Выбор тарифа → Выбор способа оплаты
                    │
          ┌─────────┴──────────┐
     Telegram Stars         ЮMoney / другой провайдер
          │                    │
   invoice_payload        Quickpay URL / редирект
          │                    │
   successful_payment     webhook POST
          │                    │
          └─────────┬──────────┘
               PaymentService
               .confirm_payment()
                    │
           SubscriptionService
           .extend_subscription()
                    │
        3x-ui клиент создан/продлён во всех INBOUND_IDS
```

Модель `Payment` единая для всех провайдеров:

| Поле | Описание |
|---|---|
| `provider` | `telegram_stars`, `yoomoney` и т.д. |
| `currency` | `XTR`, `RUB` и т.д. |
| `amount` | сумма в соответствующей валюте |
| `external_payment_id` | charge_id (Stars) или operation_id (ЮMoney) |
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

**Один из inbound'ов не найден (`/ping`):**
Проверь, что все ID из `INBOUND_IDS` существуют на панели (`/xui` покажет
список актуальных ID) и что каждый нужный inbound включён.

**ЮMoney webhook не работает:**
Проверь что домен резолвится (`dig pay.домен.ru`), сертификат есть (`ls /etc/letsencrypt/live/`), порт 443 открыт (`ufw allow 443`).

**`docker-compose: command not found`:**
```bash
sudo apt install docker-compose-v2 -y
```

---

## Требования к серверу

- Ubuntu 22.04+
- Docker 24+ и Docker Compose v2
- 3x-ui с настроенным(и) VLESS Reality/WS+TLS inbound'ом(ами)
- Для ЮMoney и аналогичных провайдеров: домен с A-записью (Cloudflare Proxy OFF)

---

## Безопасность

- Секреты только в `.env`, файл добавлен в `.gitignore`
- `ADMIN_IDS` проверяются на уровне хендлеров
- Повторная обработка платежа защищена уникальным `external_payment_id`
- Сертификат монтируется в Docker read-only
- В боте не хранятся и не запрашиваются ИНН/паспортные данные пользователей
