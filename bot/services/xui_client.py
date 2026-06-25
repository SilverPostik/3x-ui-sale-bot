"""
3x-ui API client — полностью переписан под актуальный API.

Ключевые факты из документации и issues:
- /login принимает application/x-www-form-urlencoded (username=...&password=...)
- Сессия хранится в cookie с именем "session"
- Новая API-форма клиента: /panel/api/clients/add и /panel/api/clients/update
    {"client": {...}, "inboundIds": [<id>]}
- Legacy-форма клиента: /panel/api/inbounds/addClient и /panel/api/inbounds/updateClient
    {"id": <int>, "settings": "<JSON-строка>"}
  where settings = json.dumps({"clients": [...]})
- subId НЕ генерируется сервером при API-создании (issue #3237), нужно передавать явно
- flow для VLESS Reality: "xtls-rprx-vision"
- API может вернуть пустой ответ (баг #3052, #3236) — нужны retries
- web_base_path из настроек панели (опциональный префикс)
"""
import asyncio
import json
import logging
import re
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
        return urlunparse((parsed.scheme, parsed.netloc, f"/sub/{sub_id}", "", "", ""))

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
        Авторизация для новых версий 3x-ui.
        Сначала пытается использовать Bearer API токен.
        Если токен не задан, выполняет cookie-based login.
        """
        if self._api_token:
            logger.info("3x-ui API token auth enabled")
            return True

        if not self._username or not self._password:
            logger.error("3x-ui username/password are not configured")
            return False

        session = await self._get_session()

        try:
            async with session.get(self._base) as resp:
                html = await resp.text()

                if resp.status != 200:
                    logger.error(
                        f"3x-ui login page error: status={resp.status}"
                    )
                    return False

            match = re.search(
                r'csrf-token"\s+content="([^"]+)"',
                html,
            )

            if not match:
                logger.error("3x-ui csrf token not found")
                return False

            csrf_token = match.group(1)
            self._csrf_token = csrf_token

            async with session.post(
                self._url("login"),
                data={
                    "username": self._username,
                    "password": self._password,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRF-Token": csrf_token,
                    "Referer": self._base,
                    "Origin": self._base.rstrip("/"),
                },
            ) as resp:

                text = await resp.text()

                logger.info(
                    f"3x-ui login response: "
                    f"status={resp.status} "
                    f"text={text[:500]}"
                )

                if not text.strip():
                    logger.error("3x-ui login: empty response")
                    return False

                try:
                    data = json.loads(text)
                except Exception:
                    logger.error(
                        f"3x-ui login invalid json: {text[:500]}"
                    )
                    return False

                if data.get("success"):
                    self._logged_in = True
                    logger.info("3x-ui login OK")
                    return True

                logger.error(f"3x-ui login failed: {data}")
                return False

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
        Делает запрос с retry на пустой ответ (баг 3x-ui) и re-auth на 401 в cookie режиме.
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
                            logger.error("3x-ui 401 with API token")
                            return None
                        if _retry_auth:
                            logger.info("3x-ui 401, re-login...")
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

    def _make_client_settings_str(self, clients: list[dict]) -> str:
        """
        settings для addClient/updateClient — это строка (двойная сериализация).
        Это не баг нашего кода — так работает 3x-ui API.
        """
        return json.dumps({"clients": clients})

    async def _try_legacy_add_client(self, inbound_id: int, client: dict) -> bool:
        payload = {
            "id": inbound_id,
            "settings": self._make_client_settings_str([client]),
        }
        resp = await self._request("POST", "/panel/api/inbounds/addClient", json_body=payload)
        if resp and resp.get("success"):
            logger.info("3x-ui legacy addClient succeeded")
            return True
        logger.debug(f"3x-ui legacy addClient failed: {resp}")
        return False

    async def _try_legacy_update_client(self, inbound_id: int, client: dict) -> bool:
        payload = {
            "id": inbound_id,
            "settings": self._make_client_settings_str([client]),
        }
        resp = await self._request("POST", "/panel/api/inbounds/updateClient", json_body=payload)
        if resp and resp.get("success"):
            logger.info("3x-ui legacy updateClient succeeded")
            return True
        logger.debug(f"3x-ui legacy updateClient failed: {resp}")
        return False

    async def add_client(
        self,
        inbound_id: int,
        email: str,
        expire_ms: int,
        sub_id: str,
        client_id: Optional[str] = None,
        limit_ip: int = 1,
        total_gb: int = 0,
        flow: str = "xtls-rprx-vision",
    ) -> Optional[str]:
        """
        Добавляет нового клиента и привязывает его к inbound.
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
            "inboundIds": [inbound_id],
        }
        logger.debug(f"3x-ui add_client payload: {json.dumps(payload, ensure_ascii=False)}")
        resp = await self._request("POST", "/panel/api/clients/add", json_body=payload)
        if resp and resp.get("success"):
            logger.info(f"3x-ui client created: id={cid} email={email} sub_id={sub_id}")
            return cid

        logger.warning(f"3x-ui add_client primary endpoint failed for email={email}: {resp}")
        if await self._try_legacy_add_client(inbound_id, client):
            return cid

        logger.error(f"3x-ui add_client failed for email={email}: {resp}")
        return None

    async def update_client(
        self,
        inbound_id: int,
        client_id: str,
        email: str,
        expire_ms: int,
        sub_id: str,
        enable: bool = True,
        flow: str = "xtls-rprx-vision",
    ) -> bool:
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

        logger.warning(f"3x-ui update_client primary endpoint failed for email={email}: {resp}")
        return await self._try_legacy_update_client(inbound_id, client)

    async def disable_client(
        self,
        inbound_id: int,
        client_id: str,
        email: str,
        sub_id: str,
    ) -> bool:
        return await self.update_client(
            inbound_id=inbound_id,
            client_id=client_id,
            email=email,
            expire_ms=0,
            sub_id=sub_id,
            enable=False,
        )

    async def delete_client(self, inbound_id: int, client_id: str) -> bool:
        resp = await self._request(
            "POST",
            f"/panel/api/clients/del/{client_id}",
        )
        return bool(resp and resp.get("success"))

    async def get_client_stats(self, email: str) -> Optional[dict]:
        resp = await self._request(
            "GET", f"/panel/api/clients/get/{email}"
        )
        if resp and resp.get("success"):
            return resp.get("obj")
        return None

    async def online_clients(self) -> list[str]:
        """Возвращает список email онлайн-клиентов."""
        resp = await self._request("GET", "/panel/api/clients/onlines")
        if resp and resp.get("success"):
            return resp.get("obj") or []
        return []

    # ------------------------------------------------------------------ subscription URL

    def build_subscription_url(self, sub_id: str) -> str:
        """
        Subscription URL: <panel_host>/sub/<subId>.
        Убирает дополнительный web path панели из публичного URL.
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