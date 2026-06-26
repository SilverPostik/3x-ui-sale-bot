#!/bin/bash
set -e

# ─── Цвета ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }

# ─── Параметры ───────────────────────────────────────────────────────────────
if [ -z "$1" ]; then
    echo "Использование: ./setup_webhook.sh pay.твойдомен.ru [email@mail.ru]"
    exit 1
fi

DOMAIN="$1"
EMAIL="${2:-admin@${DOMAIN}}"
ENV_FILE="$(dirname "$0")/.env"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Настройка SSL webhook для ${DOMAIN}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ─── 1. Проверка прав ────────────────────────────────────────────────────────
[ "$EUID" -ne 0 ] && fail "Запусти с правами root: sudo ./setup_webhook.sh ..."
ok "Root права"

# ─── 2. Проверка что домен указывает на этот сервер ──────────────────────────
MY_IP=$(curl -s https://api.ipify.org)
DNS_IP=$(dig +short "$DOMAIN" | tail -1)

echo "Мой IP:  ${MY_IP}"
echo "DNS IP:  ${DNS_IP}"

if [ "$MY_IP" != "$DNS_IP" ]; then
    warn "Домен ${DOMAIN} указывает на ${DNS_IP}, а не на ${MY_IP}"
    warn "Добавь A-запись в Cloudflare: ${DOMAIN} → ${MY_IP} (Proxy: OFF)"
    read -p "Продолжить всё равно? (y/N): " CONT
    [[ "$CONT" != "y" && "$CONT" != "Y" ]] && exit 1
else
    ok "DNS проверен: ${DOMAIN} → ${MY_IP}"
fi

# ─── 3. Установка certbot ─────────────────────────────────────────────────────
if ! command -v certbot &>/dev/null; then
    echo "Устанавливаю certbot..."
    apt-get update -qq
    apt-get install -y -qq certbot dnsutils curl
    ok "certbot установлен"
else
    ok "certbot уже установлен"
fi

# ─── 4. Освобождаем порт 80 для certbot ──────────────────────────────────────
# Если docker занял 80 — временно останавливаем
DOCKER_USED_80=false
if ss -tlnp | grep -q ':80 '; then
    warn "Порт 80 занят, временно останавливаю docker-compose..."
    cd "$(dirname "$0")"
    docker compose down 2>/dev/null || true
    DOCKER_USED_80=true
fi

# ─── 5. Выпуск сертификата ───────────────────────────────────────────────────
if [ -d "$CERT_DIR" ]; then
    ok "Сертификат уже существует, обновляю..."
    certbot renew --cert-name "$DOMAIN" --quiet
else
    echo "Выпускаю сертификат для ${DOMAIN}..."
    certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        -d "$DOMAIN"
fi

ok "Сертификат выпущен: ${CERT_DIR}"

# ─── 6. Обновляем .env ────────────────────────────────────────────────────────
if [ -f "$ENV_FILE" ]; then
    if grep -q "^WEBHOOK_HOST=" "$ENV_FILE"; then
        sed -i "s|^WEBHOOK_HOST=.*|WEBHOOK_HOST=https://${DOMAIN}|" "$ENV_FILE"
    else
        echo "WEBHOOK_HOST=https://${DOMAIN}" >> "$ENV_FILE"
    fi
    ok ".env обновлён: WEBHOOK_HOST=https://${DOMAIN}"
else
    warn ".env не найден рядом со скриптом, обнови вручную:"
    echo "  WEBHOOK_HOST=https://${DOMAIN}"
fi

# ─── 7. Обновляем docker-compose — порт 443 и монтирование сертов ────────────
COMPOSE_FILE="$(dirname "$0")/docker-compose.yml"
if [ -f "$COMPOSE_FILE" ]; then
    # Проверяем, не добавлено ли уже
    if ! grep -q "443:443" "$COMPOSE_FILE"; then
        warn "Обнови docker-compose.yml вручную — добавь в секцию bot:"
        echo ""
        echo "    ports:"
        echo "      - \"443:443\""
        echo "    volumes:"
        echo "      - /etc/letsencrypt:/etc/letsencrypt:ro"
        echo ""
    else
        ok "docker-compose.yml уже содержит порт 443"
    fi
fi

# ─── 8. Автообновление сертификата через cron ─────────────────────────────────
CRON_JOB="0 3 * * * certbot renew --quiet --pre-hook 'docker compose -f $(dirname "$0")/docker-compose.yml down' --post-hook 'docker compose -f $(dirname "$0")/docker-compose.yml up -d'"
(crontab -l 2>/dev/null | grep -v "certbot renew"; echo "$CRON_JOB") | crontab -
ok "Автообновление сертификата добавлено в cron (каждую ночь в 3:00)"

# ─── 9. Поднимаем обратно ─────────────────────────────────────────────────────
if [ "$DOCKER_USED_80" = true ]; then
    cd "$(dirname "$0")"
    docker compose up -d
    ok "docker-compose запущен"
fi

# ─── Итог ─────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Готово!"
echo ""
echo "Следующие шаги:"
echo "  1. Обнови docker-compose.yml (порт 443 + volume /etc/letsencrypt)"
echo "  2. Перезапусти бота: docker compose up -d --build"
echo "  3. В YooMoney укажи webhook:"
echo "     https://${DOMAIN}/yoomoney/notify"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
