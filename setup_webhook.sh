#!/bin/bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }

if [ -z "$1" ]; then
    echo "Использование: ./setup_webhook.sh pay.твойдомен.ru [email@mail.ru]"
    exit 1
fi

DOMAIN="$1"
EMAIL="${2:-admin@${DOMAIN}}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Настройка SSL webhook для ${DOMAIN}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ─── 1. Root ─────────────────────────────────────────────────────────────────
[ "$EUID" -ne 0 ] && fail "Запусти с правами root: sudo ./setup_webhook.sh ..."
ok "Root права"

# ─── 2. DNS ──────────────────────────────────────────────────────────────────
apt-get install -y -qq dnsutils curl 2>/dev/null || true
MY_IP=$(curl -s https://api.ipify.org)
DNS_IP=$(dig +short "$DOMAIN" | tail -1)
echo "Мой IP:  ${MY_IP}"
echo "DNS IP:  ${DNS_IP}"
if [ "$MY_IP" != "$DNS_IP" ]; then
    warn "Домен ${DOMAIN} → ${DNS_IP}, ожидается ${MY_IP}"
    warn "Добавь A-запись в Cloudflare: ${DOMAIN} → ${MY_IP} (Proxy: OFF)"
    read -p "Продолжить всё равно? (y/N): " CONT
    [[ "$CONT" != "y" && "$CONT" != "Y" ]] && exit 1
else
    ok "DNS: ${DOMAIN} → ${MY_IP}"
fi

# ─── 3. Certbot ──────────────────────────────────────────────────────────────
if ! command -v certbot &>/dev/null; then
    echo "Устанавливаю certbot..."
    apt-get update -qq && apt-get install -y -qq certbot
    ok "certbot установлен"
else
    ok "certbot уже установлен"
fi

# ─── 4. Освобождаем порт 80 ──────────────────────────────────────────────────
DOCKER_WAS_RUNNING=false
if ss -tlnp | grep -q ':80 '; then
    warn "Порт 80 занят — временно останавливаю docker compose..."
    cd "$SCRIPT_DIR" && docker compose down 2>/dev/null || true
    DOCKER_WAS_RUNNING=true
fi

# ─── 5. Сертификат ───────────────────────────────────────────────────────────
if [ -d "$CERT_DIR" ]; then
    certbot renew --cert-name "$DOMAIN" --quiet
    ok "Сертификат обновлён"
else
    certbot certonly --standalone --non-interactive --agree-tos --email "$EMAIL" -d "$DOMAIN"
    ok "Сертификат выпущен: ${CERT_DIR}"
fi

# ─── 6. Обновляем .env ───────────────────────────────────────────────────────
if [ -f "$ENV_FILE" ]; then
    if grep -q "^WEBHOOK_HOST=" "$ENV_FILE"; then
        sed -i "s|^WEBHOOK_HOST=.*|WEBHOOK_HOST=https://${DOMAIN}|" "$ENV_FILE"
    else
        echo "WEBHOOK_HOST=https://${DOMAIN}" >> "$ENV_FILE"
    fi
    ok ".env: WEBHOOK_HOST=https://${DOMAIN}"
else
    warn ".env не найден — добавь вручную: WEBHOOK_HOST=https://${DOMAIN}"
fi

# ─── 7. Обновляем docker-compose.yml ─────────────────────────────────────────
if [ -f "$COMPOSE_FILE" ]; then
    # Порт 443
    if ! grep -q '"443:443"' "$COMPOSE_FILE" && ! grep -q "'443:443'" "$COMPOSE_FILE" && ! grep -q "443:443" "$COMPOSE_FILE"; then
        # Заменяем "8080:8080" на два порта, или добавляем 443 после существующего ports блока
        if grep -q "8080:8080" "$COMPOSE_FILE"; then
            sed -i 's|"8080:8080"|"443:443"\n      - "8080:8080"|' "$COMPOSE_FILE"
        else
            # Добавляем ports секцию перед volumes в секции bot
            sed -i '/env_file: .env/a\    ports:\n      - "443:443"\n      - "8080:8080"' "$COMPOSE_FILE"
        fi
        ok "docker-compose.yml: добавлен порт 443"
    else
        ok "docker-compose.yml: порт 443 уже есть"
    fi

    # Volume /etc/letsencrypt
    if ! grep -q "letsencrypt" "$COMPOSE_FILE"; then
        sed -i 's|- \.:/app|- .:/app\n      - /etc/letsencrypt:/etc/letsencrypt:ro|' "$COMPOSE_FILE"
        ok "docker-compose.yml: добавлен volume /etc/letsencrypt"
    else
        ok "docker-compose.yml: volume /etc/letsencrypt уже есть"
    fi
else
    warn "docker-compose.yml не найден"
fi

# ─── 8. ufw: открываем порт 443 ──────────────────────────────────────────────
if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    ufw allow 443/tcp >/dev/null 2>&1
    ok "ufw: порт 443 открыт"
fi

# ─── 9. Cron автообновление ──────────────────────────────────────────────────
CRON_JOB="0 3 * * * certbot renew --quiet --pre-hook 'docker compose -f ${COMPOSE_FILE} down' --post-hook 'docker compose -f ${COMPOSE_FILE} up -d'"
(crontab -l 2>/dev/null | grep -v "certbot renew"; echo "$CRON_JOB") | crontab -
ok "cron: автообновление сертификата каждую ночь в 3:00"

# ─── 10. Перезапускаем бота ──────────────────────────────────────────────────
cd "$SCRIPT_DIR"
docker compose up -d --build
ok "docker compose: бот перезапущен"

# ─── Итог ────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Всё готово!"
echo ""
echo "  Укажи в YooMoney → Уведомления HTTP:"
echo "  https://${DOMAIN}/yoomoney/notify"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
