#!/bin/bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }

if [ -z "$1" ]; then
    echo "Использование: sudo ./setup_webhook.sh pay.твойдомен.ru email@mail.ru [https_port]"
    echo "  https_port — необязательно, по умолчанию 9443"
    echo "  (443 и 8443 у тебя заняты под VLESS Reality / VLESS WS+TLS — их не трогаем)"
    exit 1
fi

DOMAIN="$1"
EMAIL="${2:-admin@${DOMAIN}}"
HTTPS_PORT="${3:-9443}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
BOT_PORT=8080

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Настройка HTTPS webhook для ${DOMAIN}"
echo "  Platega требует валидный SSL-сертификат"
echo "  Схема: Platega → nginx :${HTTPS_PORT} (SSL) → бот :${BOT_PORT}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ─── 1. Root ─────────────────────────────────────────────────────────────────
[ "$EUID" -ne 0 ] && fail "Запусти с правами root: sudo ./setup_webhook.sh ..."
ok "Root права"

if [ "$HTTPS_PORT" == "443" ] || [ "$HTTPS_PORT" == "8443" ]; then
    fail "Порт ${HTTPS_PORT} занят VLESS-инбаундом 3x-ui. Укажи другой порт третьим аргументом."
fi

# ─── 2. Зависимости ──────────────────────────────────────────────────────────
apt-get update -qq
apt-get install -y -qq nginx certbot dnsutils curl 2>/dev/null
ok "nginx + certbot установлены"

# ─── 3. DNS ──────────────────────────────────────────────────────────────────
MY_IP=$(curl -s https://api.ipify.org)
DNS_IP=$(dig +short "$DOMAIN" | tail -1)
echo "Мой IP:  ${MY_IP}"
echo "DNS IP:  ${DNS_IP}"
if [ "$MY_IP" != "$DNS_IP" ]; then
    warn "Домен ${DOMAIN} → ${DNS_IP}, ожидается ${MY_IP}"
    warn "Добавь A-запись в Cloudflare: ${DOMAIN} → ${MY_IP} (Proxy: OFF, серая тучка)"
    read -p "Продолжить всё равно? (y/N): " CONT
    [[ "$CONT" != "y" && "$CONT" != "Y" ]] && exit 1
else
    ok "DNS: ${DOMAIN} → ${MY_IP}"
fi

# ─── 4. Временный nginx на :80 — только для HTTP-01 challenge ────────────────
mkdir -p /var/www/certbot
cat > /etc/nginx/sites-available/platega-acme << EOF
server {
    listen 80;
    server_name ${DOMAIN};
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 404;
    }
}
EOF
ln -sf /etc/nginx/sites-available/platega-acme /etc/nginx/sites-enabled/platega-acme
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable nginx && systemctl reload nginx
ok "nginx :80 готов к выпуску сертификата"

if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    ufw allow 80/tcp >/dev/null 2>&1
fi

# ─── 5. Получаем сертификат (только сертификат, без правки nginx-конфига) ────
if [ -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
    ok "Сертификат для ${DOMAIN} уже существует, пропускаем выпуск"
else
    certbot certonly --webroot -w /var/www/certbot \
        -d "${DOMAIN}" \
        --agree-tos -m "${EMAIL}" --non-interactive
    ok "Сертификат Let's Encrypt выпущен"
fi

# ─── 6. Финальный nginx-конфиг: HTTPS на отдельном порту → бот ───────────────
cat > /etc/nginx/sites-available/platega << EOF
server {
    listen ${HTTPS_PORT} ssl;
    server_name ${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    location /platega/notify {
        proxy_pass http://127.0.0.1:${BOT_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    location / {
        return 404;
    }
}
EOF
ln -sf /etc/nginx/sites-available/platega /etc/nginx/sites-enabled/platega
rm -f /etc/nginx/sites-enabled/platega-acme  # ACME-конфиг на :80 больше не нужен
nginx -t && systemctl reload nginx
ok "nginx настроен: :${HTTPS_PORT} (SSL) /platega/notify → :${BOT_PORT}"

# ─── 7. ufw ──────────────────────────────────────────────────────────────────
if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    ufw allow ${HTTPS_PORT}/tcp >/dev/null 2>&1
    ok "ufw: порт ${HTTPS_PORT} открыт"
fi

# ─── 8. Автообновление сертификата ────────────────────────────────────────────
cat > /etc/cron.d/certbot-platega << EOF
0 3 * * * root certbot renew --quiet --webroot -w /var/www/certbot --deploy-hook "systemctl reload nginx"
EOF
ok "Автообновление сертификата настроено (ежедневно в 03:00)"

# ─── 9. Обновляем .env ────────────────────────────────────────────────────────
WEBHOOK_URL="https://${DOMAIN}:${HTTPS_PORT}"
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

# ─── 10. Перезапускаем бота ───────────────────────────────────────────────────
cd "$SCRIPT_DIR"
docker compose up -d --build
ok "docker compose: бот перезапущен"

# ─── Итог ────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Всё готово!"
echo ""
echo "  Укажи в личном кабинете Platega → Настройки → Callback URLs:"
echo "  ${WEBHOOK_URL}/platega/notify"
echo ""
echo "  ⚠️  Порты на сервере:"
echo "   :443       — VLESS Reality (3x-ui, не трогаем)"
echo "   :8443      — VLESS WS+TLS (3x-ui, не трогаем)"
echo "   :${HTTPS_PORT} — nginx SSL → бот (Platega webhook)"
echo "   :8080      — бот (только localhost, снаружи закрыт)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
