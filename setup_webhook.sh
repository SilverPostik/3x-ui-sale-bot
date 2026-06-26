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
BOT_PORT=8080

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Настройка webhook для ${DOMAIN}"
echo "  Схема: YooMoney → nginx :80 → бот :${BOT_PORT}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ─── 1. Root ─────────────────────────────────────────────────────────────────
[ "$EUID" -ne 0 ] && fail "Запусти с правами root: sudo ./setup_webhook.sh ..."
ok "Root права"

# ─── 2. Зависимости ──────────────────────────────────────────────────────────
apt-get install -y -qq nginx dnsutils curl 2>/dev/null
ok "nginx установлен"

# ─── 3. DNS ──────────────────────────────────────────────────────────────────
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

# ─── 4. nginx: проксируем /yoomoney/notify на бота ───────────────────────────
cat > /etc/nginx/sites-available/yoomoney << EOF
server {
    listen 80;
    server_name ${DOMAIN};

    # Только webhook — всё остальное не трогаем
    location /yoomoney/notify {
        proxy_pass http://127.0.0.1:${BOT_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    # Всё остальное — 404
    location / {
        return 404;
    }
}
EOF

ln -sf /etc/nginx/sites-available/yoomoney /etc/nginx/sites-enabled/yoomoney
# Убираем дефолтный сайт если есть
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable nginx && systemctl reload nginx
ok "nginx настроен: :80/yoomoney/notify → :${BOT_PORT}"

# ─── 5. ufw ──────────────────────────────────────────────────────────────────
if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    ufw allow 80/tcp >/dev/null 2>&1
    ok "ufw: порт 80 открыт"
fi

# ─── 6. Обновляем .env ───────────────────────────────────────────────────────
# YooMoney webhook URL будет http (без SSL) — это нормально для HTTP-уведомлений
WEBHOOK_URL="http://${DOMAIN}"
if [ -f "$ENV_FILE" ]; then
    if grep -q "^WEBHOOK_HOST=" "$ENV_FILE"; then
        sed -i "s|^WEBHOOK_HOST=.*|WEBHOOK_HOST=${WEBHOOK_URL}|" "$ENV_FILE"
    else
        echo "WEBHOOK_HOST=${WEBHOOK_URL}" >> "$ENV_FILE"
    fi
    ok ".env: WEBHOOK_HOST=${WEBHOOK_URL}"
else
    warn ".env не найден — добавь вручную: WEBHOOK_HOST=${WEBHOOK_URL}"
fi

# ─── 7. docker-compose: только порт 8080 ─────────────────────────────────────
if [ -f "$COMPOSE_FILE" ]; then
    sed -i '/"443:443"/d' "$COMPOSE_FILE"
    sed -i "/'443:443'/d" "$COMPOSE_FILE"
    sed -i '/letsencrypt/d' "$COMPOSE_FILE"
    if ! grep -q "8080:8080" "$COMPOSE_FILE"; then
        sed -i '/env_file: .env/a\    ports:\n      - "127.0.0.1:8080:8080"' "$COMPOSE_FILE"
    else
        # Убеждаемся что порт доступен только локально (не снаружи)
        sed -i 's|"8080:8080"|"127.0.0.1:8080:8080"|' "$COMPOSE_FILE"
        sed -i "s|'8080:8080'|'127.0.0.1:8080:8080'|" "$COMPOSE_FILE"
    fi
    ok "docker-compose.yml: бот слушает только на 127.0.0.1:8080"
fi

# ─── 8. Перезапускаем бота ───────────────────────────────────────────────────
cd "$SCRIPT_DIR"
docker compose up -d --build
ok "docker compose: бот перезапущен"

# ─── Итог ────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Всё готово!"
echo ""
echo "  Укажи в YooMoney → Уведомления HTTP:"
echo "  http://${DOMAIN}/yoomoney/notify"
echo ""
echo "  ⚠️  Порты на сервере:"
echo "   :443  — VLESS инбаунд (3x-ui, не трогаем)"
echo "   :8443 — VLESS WS+TLS инбаунд (3x-ui, не трогаем)"
echo "   :80   — nginx → бот (webhook)"
echo "   :8080 — бот (только localhost, снаружи закрыт)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
