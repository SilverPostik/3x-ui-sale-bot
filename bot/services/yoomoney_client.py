"""
YooMoney (ЮMoney) payment provider.
Использует YooMoney Quickpay (форма оплаты без регистрации магазина).
Для production нужен YooMoney OAuth токен получателя.
"""
import hashlib
import logging
from typing import Optional
import aiohttp
from config.settings import settings

logger = logging.getLogger(__name__)

YOOMONEY_NOTIFICATION_SECRET = settings.YOOMONEY_SECRET


def build_payment_url(
    receiver: str,
    amount: float,
    label: str,
    payment_type: str = "PC",  # PC = кошелёк, AC = карта
    comment: str = "",
) -> str:
    """
    Формирует ссылку на оплату через YooMoney Quickpay.
    receiver — номер кошелька YooMoney получателя.
    label — уникальный идентификатор платежа (payment_id из БД).
    """
    import urllib.parse
    params = {
        "receiver": receiver,
        "quickpay-form": "button",
        "paymentType": payment_type,
        "sum": f"{amount:.2f}",
        "label": label,
        "comment": comment,
        "targets": comment or f"VPN подписка #{label}",
    }
    query = urllib.parse.urlencode(params)
    return f"https://yoomoney.ru/quickpay/confirm?{query}"


def verify_notification(data: dict) -> bool:
    """
    Проверяет подпись уведомления от YooMoney.
    https://yoomoney.ru/docs/payment-buttons/using-api/notifications
    """
    secret = YOOMONEY_NOTIFICATION_SECRET
    if not secret:
        logger.warning("YOOMONEY_SECRET not set, skipping signature check")
        return True

    fields = [
        data.get("notification_type", ""),
        data.get("operation_id", ""),
        data.get("amount", ""),
        data.get("currency", ""),
        data.get("datetime", ""),
        data.get("sender", ""),
        data.get("codepro", ""),
        secret,
        data.get("label", ""),
    ]
    raw = "&".join(fields)
    expected = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    received = data.get("sha1_hash", "")
    ok = expected == received
    if not ok:
        logger.warning(f"YooMoney signature mismatch. expected={expected} got={received}")
    return ok
