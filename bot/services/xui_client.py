"""
3x-ui API client — переписан под актуальный REST API панели версии 3.x
(проверено по официальной OpenAPI-схеме /panel/api/openapi.json для 3.4.2).

Ключевые факты, подтверждённые схемой:
- Клиенты — самостоятельные сущности (ClientRecord), не встроены в JSON inbound'а.
  Все операции с клиентами живут под /panel/api/clients/*.
- Старый "legacy" API (/panel/api/inbounds/addClient, /updateClient) в 3.x
  ОТСУТСТВУЕТ — в текущей OpenAPI-схеме под /panel/api/inbounds таких путей
  больше нет, поэтому никакого fallback на него быть не может.
- POST /panel/api/clients/add — тело {"client": {...}, "inboundIds": [...]}.
  Создаёт клиента и сразу привязывает к списку inbound'ов за один вызов
  (bulkCreate использует тот же формат {client, inboundIds} поэлементно).
- POST /panel/api/clients/update/{email} — тело это сам объект клиента
  (без обёртки client/inboundIds). Сервер ЗАМЕНЯЕТ строку целиком, поэтому
  нужно передавать все поля, которые должны сохраниться. Изменения сами
  распространяются на все inbound'ы, к которым клиент уже привязан —
  отдельно указывать inboundIds для update не нужно.
- POST /panel/api/clients/{email}/attach и .../detach — привязка/отвязка
  существующего клиента к дополнительным inbound'ам без пересоздания.
- POST /panel/api/clients/del/{email} — удаление клиента по email (не по UUID).
- GET /panel/api/clients/get/{email} — данные клиента + список привязанных
  inbound ID.
- POST /panel/api/clients/onlines — теперь POST, а не GET.
- Авторизация: Bearer-токен (Settings → Security → API Token) — рекомендуемый
  способ, полностью пропускает CSRF. Токены хранятся в панели как SHA-256
  хэш и показываются один раз при создании — именно это значение нужно
  положить в THREEXUI_API_TOKEN.
  Cookie-режим (username/password) как запасной вариант: POST /login,
  затем GET /csrf-token — токен нужно передавать в заголовке X-CSRF-Token
  на всех "небезопасных" (изменяющих) запросах. Формат тела /login не
  зафиксирован в текстовом описании схемы (там нет explicit request body
  schema) — если авторизация по логину/паролю не заработает, сверьте
  реальную форму запроса на вкладке /panel/api-docs → /login → Try it out
  на вашей панели и поправьте `login()` ниже.
"""
import asyncio
import json
import logging
import uuid
from typing import Optional
from urllib.parse import urlparse, urlunparse

import aiohttp
from config.settings import settings

logger = logging.getLogger(__name__)

_RETRY_COUNT = 3
_RETRY_DELAY = 1.0  # seconds


class XUIClient:
    def __init__(self) -> None:
        self._base = settings.THREEXUI_URL.rstrip("/")
        self._username = settings.THREEXUI_USERNAME
        self._password = settings.THREEXUI_PASSWORD
        self._api_token = settings.THREEXUI_API_TOKEN
        self._session: Optional[aiohttp.ClientSession] = None
        self._logged_in: bool = False
        self._csrf_token: str | None = None

    def _url(self, path: str) -> str:
        return f"{self._base}/{path.lstrip('/')}"

    def _subscription_url(self, sub_id: str) -> str:
        parsed = urlparse(self._base)
        host = parsed.hostname  # только IP/домен без порта
        port = settings.THREEXUI_SUB_PORT
        netloc = f"{host}:{port}"
        return urlunparse((parsed.scheme, netloc, f"/sub/{sub_id}", "", "", ""))

    # ------------------------------------------------------------------ session

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # unsafe=True обязателен, если URL задан по IP (без доменного имени)
            jar = aiohttp.CookieJar(unsafe=True)
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(
                cookie_jar=jar,
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30),
            )
            self._logged_in = False
        return self._session

    async def login(self) -> bool:
        """
        Bearer-токен (рекомендуется) полностью пропускает эту функцию —
        см. _ensure_login(). Cookie-режим — запасной вариант для панелей
        без выпущенного API-токена.
        """
        if self._api_token:
            logger.info("3x-ui: используется Bearer API-токен, cookie-логин не нужен")
            return True

        if not self._username or not self._password:
            logger.error("3x-ui: не заданы ни THREEXUI_API_TOKEN, ни username/password")
            return False

        session = await self._get_session()

        try:
            async with session.post(
                self._url("login"),
                json={"username": self._username, "password": self._password},
                headers={"Accept": "application/json"},
            ) as resp:
                text = await resp.text()
                logger.info(f"3x-ui login response: status={resp.status} text={text[:300]}")

                if not text.strip():
                    logger.error("3x-ui login: пустой ответ")
                    return False

                try:
                    data = json.loads(text)
                except Exception:
                    logger.error(f"3x-ui login: невалидный JSON: {text[:300]}")
                    return False

                if not data.get("success"):
                    logger.error(f"3x-ui login failed: {data}")
                    return False

            # После успешного логина получаем CSRF-токен для последующих
            # изменяющих запросов (POST/DELETE) в cookie-режиме.
            async with session.get(
                self._url("csrf-token"), headers={"Accept": "application/json"}
            ) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text)
                except Exception:
                    data = None
                token = (data or {}).get("obj") if isinstance(data, dict) else None
                if isinstance(token, dict):
                    token = token.get("token")
                if token:
                    self._csrf_token = token
                else:
                    logger.warning(f"3x-ui: не удалось получить csrf-token: {text[:300]}")

            self._logged_in = True
            logger.info("3x-ui login OK (cookie mode)")
            return True

        except Exception as e:
            logger.exception(f"3x-ui login exception: {e}")
            return False

    async def _ensure_login(self) -> bool:
        if self._api_token:
            return True
        if not self._logged_in:
            return await self.login()
        return True

    # ------------------------------------------------------------------ raw request

    def _auth_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        elif self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[dict] = None,
        _retry_auth: bool = True,
    ) -> Optional[dict]:
        """
        Делает запрос с retry на пустой ответ и re-auth на 401 в cookie-режиме.
        """
        await self._ensure_login()
        session = await self._get_session()
        url = self._url(path)
        text: str = ""

        for attempt in range(1, _RETRY_COUNT + 1):
            try:
                logger.debug(
                    f"3x-ui request [{attempt}/{_RETRY_COUNT}] "
                    f"{method} {url} body={json_body}"
                )
                async with session.request(
                    method,
                    url,
                    json=json_body,
                    headers=self._auth_headers(),
                ) as resp:
                    text = await resp.text()
                    logger.debug(
                        f"3x-ui response [{attempt}/{_RETRY_COUNT}] "
                        f"{method} {url} status={resp.status} text={text[:1000]}"
                    )

                    if not text.strip():
                        logger.warning(
                            f"3x-ui empty response [{attempt}/{_RETRY_COUNT}] "
                            f"{method} {path}"
                        )
                        if attempt < _RETRY_COUNT:
                            await asyncio.sleep(_RETRY_DELAY)
                            continue
                        return None

                    if resp.status == 401:
                        if self._api_token:
                            logger.error("3x-ui 401 с Bearer-токеном — проверьте THREEXUI_API_TOKEN")
                            return None
                        if _retry_auth:
                            logger.info("3x-ui 401, повторный логин...")
                            self._logged_in = False
                            if await self.login():
                                return await self._request(
                                    method, path, json_body, _retry_auth=False
                                )
                            return None

                    data = json.loads(text)
                    if not data.get("success"):
                        logger.warning(f"3x-ui {method} {path} -> {data.get('msg')}")
                    return data

            except json.JSONDecodeError as e:
                logger.error(f"3x-ui JSON decode error: {e} | text={text[:200]}")
                return None
            except Exception as e:
                logger.error(f"3x-ui request error [{attempt}] {method} {path}: {e}")
                if attempt < _RETRY_COUNT:
                    await asyncio.sleep(_RETRY_DELAY)

        return None

    # ------------------------------------------------------------------ inbounds

    async def get_inbounds(self) -> list[dict]:
        resp = await self._request("GET", "/panel/api/inbounds/list")
        if resp and resp.get("success"):
            return resp.get("obj") or []
        return []

    async def get_inbound(self, inbound_id: int) -> Optional[dict]:
        resp = await self._request("GET", f"/panel/api/inbounds/get/{inbound_id}")
        if resp and resp.get("success"):
            return resp.get("obj")
        return None

    # ------------------------------------------------------------------ clients

    async def add_client(
        self,
        inbound_ids: list[int],
        email: str,
        expire_ms: int,
        sub_id: str,
        client_id: Optional[str] = None,
        limit_ip: int = 1,
        total_gb: int = 0,
        flow: str = "xtls-rprx-vision",
    ) -> Optional[str]:
        """
        Создаёт клиента и сразу привязывает его ко всем inbound'ам из
        inbound_ids за один вызов POST /panel/api/clients/add.
        Возвращает client_id (UUID) при успехе, None при ошибке.
        """
        cid = client_id or str(uuid.uuid4())
        client = {
            "id": cid,
            "email": email,
            "flow": flow,
            "limitIp": limit_ip,
            "totalGB": total_gb,
            "expiryTime": expire_ms,
            "enable": True,
            "tgId": 0,
            "subId": sub_id,
            "comment": "",
            "reset": 0,
        }
        payload = {
            "client": client,
            "inboundIds": inbound_ids,
        }
        logger.debug(f"3x-ui add_client payload: {json.dumps(payload, ensure_ascii=False)}")
        resp = await self._request("POST", "/panel/api/clients/add", json_body=payload)
        if resp and resp.get("success"):
            logger.info(
                f"3x-ui client created: id={cid} email={email} "
                f"sub_id={sub_id} inbounds={inbound_ids}"
            )
            return cid

        logger.error(f"3x-ui add_client failed for email={email}: {resp}")
        return None

    async def update_client(
        self,
        client_id: str,
        email: str,
        expire_ms: int,
        sub_id: str,
        enable: bool = True,
        flow: str = "xtls-rprx-vision",
    ) -> bool:
        """
        Обновляет клиента по email. Изменения сами применяются ко всем
        inbound'ам, к которым клиент уже привязан — передавать inbound_ids
        не требуется (в отличие от add_client).
        """
        client = {
            "id": client_id,
            "email": email,
            "flow": flow,
            "expiryTime": expire_ms,
            "enable": enable,
            "subId": sub_id,
        }
        logger.debug(f"3x-ui update_client payload: {json.dumps(client, ensure_ascii=False)}")
        resp = await self._request(
            "POST",
            f"/panel/api/clients/update/{email}",
            json_body=client,
        )
        if resp and resp.get("success"):
            return True

        logger.error(f"3x-ui update_client failed for email={email}: {resp}")
        return False

    async def disable_client(
        self,
        client_id: str,
        email: str,
        sub_id: str,
    ) -> bool:
        return await self.update_client(
            client_id=client_id,
            email=email,
            expire_ms=0,
            sub_id=sub_id,
            enable=False,
        )

    async def attach_client(self, email: str, inbound_ids: list[int]) -> bool:
        """
        Привязывает уже существующего клиента к дополнительным inbound'ам
        (например, если админ расширил INBOUND_IDS после того, как у части
        пользователей уже были выданы подписки).
        """
        resp = await self._request(
            "POST",
            f"/panel/api/clients/{email}/attach",
            json_body={"inboundIds": inbound_ids},
        )
        return bool(resp and resp.get("success"))

    async def detach_client(self, email: str, inbound_ids: list[int]) -> bool:
        resp = await self._request(
            "POST",
            f"/panel/api/clients/{email}/detach",
            json_body={"inboundIds": inbound_ids},
        )
        return bool(resp and resp.get("success"))

    async def delete_client(self, email: str) -> bool:
        resp = await self._request("POST", f"/panel/api/clients/del/{email}")
        return bool(resp and resp.get("success"))

    async def get_client_stats(self, email: str) -> Optional[dict]:
        resp = await self._request("GET", f"/panel/api/clients/get/{email}")
        if resp and resp.get("success"):
            return resp.get("obj")
        return None

    async def online_clients(self) -> list[str]:
        """Возвращает список email онлайн-клиентов (метод — POST)."""
        resp = await self._request("POST", "/panel/api/clients/onlines")
        if resp and resp.get("success"):
            return resp.get("obj") or []
        return []

    # ------------------------------------------------------------------ subscription URL

    def build_subscription_url(self, sub_id: str) -> str:
        """
        Subscription URL отдаётся отдельным сервером подписок (не /panel/api),
        поэтому путь /sub/<subId> и отдельный порт (THREEXUI_SUB_PORT) не
        затронуты изменениями в /panel/api/clients.
        """
        return self._subscription_url(sub_id)

    # ------------------------------------------------------------------ diagnostics

    async def ping(self) -> bool:
        """Быстрая проверка соединения и авторизации."""
        inbounds = await self.get_inbounds()
        return isinstance(inbounds, list)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# Глобальный singleton
xui_client = XUIClient()
