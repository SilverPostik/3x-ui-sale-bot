"""
Platega.io — платёжный провайдер (СБП, карточный эквайринг, криптовалюта).
Документация: https://docs.platega.io/

Базовый URL: https://app.platega.io/
Авторизация — заголовки X-MerchantId / X-Secret (выдаются менеджером Platega
или доступны в личном кабинете на странице «Настройки»).

Основные эндпоинты:
  POST /transaction/process   — создание транзакции (ссылка на оплату)
  GET  /transaction/{id}      — проверка статуса транзакции

Callback (webhook) присылается провайдером на URL, указанный в ЛК
(Настройки → Callback URLs), с теми же заголовками X-MerchantId/X-Secret
и телом {"id", "amount", "currency", "status", "paymentMethod"}.
Статусы: CONFIRMED (успех), CANCELED (неуспех), CHARGEBACKED (возврат).
"""
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

import aiohttp

from config.settings import settings

logger = logging.getLogger(__name__)

PLATEGA_BASE_URL = "https://app.platega.io"


class PlategaError(Exception):
    """Базовая ошибка Platega API."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class PlategaTransaction:
    transaction_id: str
    status: str
    redirect: Optional[str] = None
    qr: Optional[str] = None
    usdt_rate: Optional[float] = None


class PlategaClient:
    """Асинхронный клиент Platega.io API."""

    def __init__(
        self,
        merchant_id: str = "",
        secret: str = "",
        base_url: str = PLATEGA_BASE_URL,
    ) -> None:
        self.merchant_id = merchant_id or settings.PLATEGA_MERCHANT_ID
        self.secret = secret or settings.PLATEGA_SECRET
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict:
        return {
            "X-MerchantId": self.merchant_id,
            "X-Secret": self.secret,
            "Content-Type": "application/json",
        }

    async def create_transaction(
        self,
        payment_method: int,
        amount: float,
        currency: str = "RUB",
        description: str = "",
        return_url: str = "",
        failed_url: str = "",
        payload: str = "",
        metadata: Optional[dict] = None,
    ) -> PlategaTransaction:
        """
        Создаёт транзакцию и возвращает ссылку на оплату.
        ID транзакции генерируется системой Platega автоматически —
        поле id в запрос не передаём.
        """
        body: dict = {
            "paymentMethod": payment_method,
            "paymentDetails": {
                "amount": amount,
                "currency": currency,
            },
            "description": description,
        }
        if return_url:
            body["return"] = return_url
        if failed_url:
            body["failedUrl"] = failed_url
        if payload:
            body["payload"] = payload
        if metadata:
            body["metadata"] = metadata

        url = f"{self.base_url}/transaction/process"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=self._headers()) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    logger.error(f"Platega create_transaction error {resp.status}: {data}")
                    raise PlategaError(f"Platega API error: {data}", status_code=resp.status)

        return PlategaTransaction(
            transaction_id=data.get("transactionId", ""),
            status=data.get("status", "PENDING"),
            redirect=data.get("redirect"),
            usdt_rate=data.get("usdtRate"),
        )

    async def get_transaction_status(self, transaction_id: str) -> PlategaTransaction:
        """Возвращает статус и детали транзакции по её id."""
        url = f"{self.base_url}/transaction/{transaction_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers()) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    logger.error(f"Platega get_transaction_status error {resp.status}: {data}")
                    raise PlategaError(f"Platega API error: {data}", status_code=resp.status)

        return PlategaTransaction(
            transaction_id=data.get("id", transaction_id),
            status=data.get("status", "PENDING"),
            qr=data.get("qr"),
        )

    def verify_callback_auth(self, merchant_id: str, secret: str) -> bool:
        """
        Проверяет заголовки X-MerchantId/X-Secret входящего callback-запроса.
        Platega не подписывает тело запроса — аутентификация именно по этим
        двум заголовкам, которые должны совпадать с вашими учётными данными.
        """
        return merchant_id == self.merchant_id and secret == self.secret


def new_external_id() -> str:
    """Генерирует уникальный внешний id для payload/трейсинга платежа."""
    return str(uuid.uuid4())


platega_client = PlategaClient()
