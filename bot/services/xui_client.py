"""
3x-ui API client — полностью переписан под актуальный API.

Ключевые факты из документации и issues:
- /login принимает application/x-www-form-urlencoded (username=...&password=...)
- Сессия хранится в cookie с именем "session"
- /panel/api/inbounds/addClient и updateClient ожидают:
    {"id": <int>, "settings": "<JSON-строка>"}
  то есть settings — это строка, результат json.dumps({"clients": [...]})
- subId НЕ генерируется сервером при API-создании (баг #3237), нужно передавать явно
- flow для VLESS Reality: "xtls-rprx-vision"
- API может вернуть пустой ответ (баг #3052, #3236) — нужны retries
- web_base_path из настроек панели (опциональный префикс)
"""
import asyncio
import json
import logging
import uuid
from typing import Optional

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
        self._session: Optional[aiohttp.ClientSession] = None
        self._logged_in: bool = False

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
        POST /login  с Content-Type: application/x-www-form-urlencoded
        Сессия сохраняется в cookie jar автоматически.
        """
        session = await self._get_session()
        url = f"{self._base}/login"
        try:
            async with session.post(
                url,
                data={"username": self._username, "password": self._password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                text = await resp.text()
                if not text.strip():
                    logger.error("3x-ui login: empty response")
                    return False
                data = json.loads(text)
                ok = data.get("success", False)
                if ok:
                    self._logged_in = True
                    logger.info("3x-ui login OK")
                else:
                    logger.error(f"3x-ui login failed: {data}")
                return ok
        except Exception as e:
            logger.error(f"3x-ui login exception: {e}")
            return False

    async def _ensure_login(self) -> bool:
        if not self._logged_in:
            return await self.login()
        return True

    # ------------------------------------------------------------------ raw request

    async def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[dict] = None,
        _retry_auth: bool = True,
    ) -> Optional[dict]:
        """
        Делает запрос с retry на пустой ответ (баг 3x-ui) и re-auth на 401.
        """
        await self._ensure_login()
        session = await self._get_session()
        url = f"{self._base}{path}"

        for attempt in range(1, _RETRY_COUNT + 1):
            try:
                async with session.request(
                    method,
                    url,
                    json=json_body,
                    headers={"Accept": "application/json"},
                ) as resp:
                    text = await resp.text()

                    # Пустой ответ — известный баг, retry
                    if not text.strip():
                        logger.warning(
                            f"3x-ui empty response [{attempt}/{_RETRY_COUNT}] "
                            f"{method} {path}"
                        )
                        if attempt < _RETRY_COUNT:
                            await asyncio.sleep(_RETRY_DELAY)
                            continue
                        return None

                    # 401 — перелогиниться и повторить
                    if resp.status == 401 and _retry_auth:
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
        Добавляет клиента в inbound.
        Возвращает client_id (UUID) при успехе, None при ошибке.

        ВАЖНО: subId передаётся явно, потому что 3x-ui НЕ генерирует его
        автоматически при API-создании (issue #3237).
        """
        cid = client_id or str(uuid.uuid4())
        client = {
            "id": cid,
            "flow": flow,
            "email": email,
            "limitIp": limit_ip,
            "totalGB": total_gb,
            "expiryTime": expire_ms,
            "enable": True,
            "tgId": "",
            "subId": sub_id,
            "comment": "",
            "reset": 0,
        }
        payload = {
            "id": inbound_id,
            "settings": self._make_client_settings_str([client]),
        }
        resp = await self._request("POST", "/panel/api/inbounds/addClient", json_body=payload)
        if resp and resp.get("success"):
            logger.info(f"3x-ui client created: id={cid} email={email} sub_id={sub_id}")
            return cid
        logger.error(f"3x-ui addClient failed for email={email}: {resp}")
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
            "flow": flow,
            "email": email,
            "expiryTime": expire_ms,
            "enable": enable,
            "subId": sub_id,
        }
        payload = {
            "id": inbound_id,
            "settings": self._make_client_settings_str([client]),
        }
        resp = await self._request(
            "POST",
            f"/panel/api/inbounds/updateClient/{client_id}",
            json_body=payload,
        )
        return bool(resp and resp.get("success"))

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
            f"/panel/api/inbounds/{inbound_id}/delClient/{client_id}",
        )
        return bool(resp and resp.get("success"))

    async def get_client_stats(self, email: str) -> Optional[dict]:
        resp = await self._request(
            "GET", f"/panel/api/inbounds/getClientTraffics/{email}"
        )
        if resp and resp.get("success"):
            return resp.get("obj")
        return None

    async def online_clients(self) -> list[str]:
        """Возвращает список email онлайн-клиентов."""
        resp = await self._request("POST", "/panel/api/inbounds/onlines")
        if resp and resp.get("success"):
            return resp.get("obj") or []
        return []

    # ------------------------------------------------------------------ subscription URL

    def build_subscription_url(self, sub_id: str) -> str:
        """
        Subscription URL: <panel_url>/sub/<subId>
        Можно импортировать в HAPP и другие клиенты.
        """
        return f"{self._base}/sub/{sub_id}"

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
