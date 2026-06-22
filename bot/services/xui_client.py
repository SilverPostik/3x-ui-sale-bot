"""
3x-ui API client. Uses only the official REST API, no web scraping.
Передаёт settings как dict (не JSON-строку) — это ключевое исправление.
"""
import uuid
import json
import logging
from typing import Optional
import aiohttp
from config.settings import settings

logger = logging.getLogger(__name__)


class XUIClient:
    def __init__(self) -> None:
        self.base_url = settings.THREEXUI_URL.rstrip("/")
        self.username = settings.THREEXUI_USERNAME
        self.password = settings.THREEXUI_PASSWORD
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)  # unsafe=True нужен для IP-адресов
            self._session = aiohttp.ClientSession(cookie_jar=jar)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> bool:
        if settings.THREEXUI_API_TOKEN:
            logger.info("3x-ui API token auth enabled")
            return True

        session = await self._get_session()
        for path in ("/loginAuthenticate", "/login"):
            try:
                async with session.post(
                    f"{self.base_url}{path}",
                    data={"username": self.username, "password": self.password},
                    headers={"Accept": "application/json"},
                    ssl=False,
                    allow_redirects=True,
                ) as resp:
                    text = await resp.text()
                    data = None
                    try:
                        data = await resp.json(content_type=None)
                    except Exception as e:
                        logger.debug(
                            "3x-ui %s parse warning: %s, status=%s, headers=%s, body=%s",
                            path,
                            e,
                            resp.status,
                            dict(resp.headers),
                            text,
                        )

                    cookies = session.cookie_jar.filter_cookies(self.base_url)
                    if data is None:
                        if resp.status in (200, 302, 303, 307, 308) and cookies:
                            logger.info(
                                "3x-ui login successful by cookie set on %s, status=%s",
                                path,
                                resp.status,
                            )
                            await self._refresh_csrf_token()
                            return True
                        logger.warning(
                            "3x-ui login %s did not return JSON: status=%s, body=%s",
                            path,
                            resp.status,
                            text,
                        )
                        if path == "/login":
                            return False
                        continue

                    if not isinstance(data, dict):
                        logger.warning(
                            "3x-ui login %s returned unexpected type %s",
                            path,
                            type(data).__name__,
                        )
                        if path == "/login":
                            return False
                        continue

                    if data.get("success"):
                        logger.info("3x-ui login successful")
                        await self._refresh_csrf_token()
                        return True

                    if resp.status in (200, 302, 303, 307, 308) and cookies:
                        logger.info(
                            "3x-ui login successful by cookie set on %s with payload, status=%s",
                            path,
                            resp.status,
                        )
                        await self._refresh_csrf_token()
                        return True

                    logger.warning(
                        "3x-ui login %s failed: status=%s, body=%s",
                        path,
                        resp.status,
                        data,
                    )
                    if path == "/login":
                        return False
            except Exception as e:
                logger.error("3x-ui login exception %s: %s", path, e)
                if path == "/login":
                    return False
        return False

    async def _refresh_csrf_token(self) -> None:
        if settings.THREEXUI_API_TOKEN:
            self._csrf_token = None
            return

        session = await self._get_session()
        try:
            async with session.get(
                f"{self.base_url}/csrf-token",
                headers={"Accept": "application/json"},
                ssl=False,
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    logger.warning("3x-ui csrf-token failed: status=%s body=%s", resp.status, text)
                    self._csrf_token = None
                    return
                data = None
                try:
                    data = await resp.json(content_type=None)
                except Exception as e:
                    logger.warning("3x-ui csrf-token parse error: %s body=%s", e, text)
                    self._csrf_token = None
                    return

                if isinstance(data, dict):
                    self._csrf_token = (
                        data.get("obj")
                        or data.get("csrfToken")
                        or data.get("token")
                        or data.get("data")
                    )
                    if isinstance(self._csrf_token, dict):
                        self._csrf_token = self._csrf_token.get("csrfToken") or self._csrf_token.get("token")
                    if not isinstance(self._csrf_token, str):
                        self._csrf_token = None
                else:
                    self._csrf_token = None
        except Exception as e:
            logger.warning("3x-ui csrf-token exception: %s", e)
            self._csrf_token = None

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict] = None,
        retry: bool = True,
    ) -> Optional[dict]:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if settings.THREEXUI_API_TOKEN:
            headers["Authorization"] = f"Bearer {settings.THREEXUI_API_TOKEN}"
        elif getattr(self, "_csrf_token", None):
            headers["X-CSRF-Token"] = self._csrf_token

        try:
            async with session.request(
                method, url, json=json_data, headers=headers, ssl=False
            ) as resp:
                if resp.status == 401 and retry and not settings.THREEXUI_API_TOKEN:
                    logged_in = await self.login()
                    if logged_in:
                        return await self._request(method, path, json_data, retry=False)
                    return None

                text = await resp.text()
                try:
                    data = await resp.json(content_type=None)
                except Exception as e:
                    logger.error(
                        "3x-ui request parse error %s %s %s: %s",
                        method,
                        path,
                        resp.status,
                        e,
                    )
                    logger.debug("3x-ui response body: %s", text)
                    return None

                if not isinstance(data, dict):
                    logger.error(
                        "3x-ui request returned unexpected response type %s %s %s: %s",
                        method,
                        path,
                        resp.status,
                        type(data).__name__,
                    )
                    logger.debug("3x-ui response body: %s", text)
                    return None

                if not data.get("success"):
                    logger.warning(f"3x-ui {method} {path} -> {data}")
                return data
        except Exception as e:
            logger.error(f"3x-ui request error {method} {path}: {e}")
            return None

    # ---------- Inbound ----------

    async def get_inbounds(self) -> list[dict]:
        resp = await self._request("GET", "/panel/api/inbounds/list")
        if resp and resp.get("success"):
            return resp.get("obj", [])
        return []

    async def get_inbound(self, inbound_id: int) -> Optional[dict]:
        resp = await self._request("GET", f"/panel/api/inbounds/get/{inbound_id}")
        if resp and resp.get("success"):
            return resp.get("obj")
        return None

    # ---------- Clients ----------

    async def add_client(
        self,
        inbound_id: int,
        email: str,
        expire_ms: int,
        sub_id: str,
        limit_ip: int = 1,
        total_gb: int = 0,
        client_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Добавляет клиента в inbound. Возвращает UUID клиента при успехе.
        sub_id передаётся в поле subId — используется для subscription URL.
        """
        cid = client_id or str(uuid.uuid4())
        # ВАЖНО: settings передаётся как dict (не JSON-строка) — это требование 3x-ui API
        client_settings = {
            "clients": [{
                "id": cid,
                "email": email,
                "limitIp": limit_ip,
                "totalGB": total_gb,
                "expiryTime": expire_ms,
                "enable": True,
                "tgId": "",
                "subId": sub_id,
            }]
        }
        payload = {"id": inbound_id, "settings": client_settings}
        resp = await self._request("POST", "/panel/api/inbounds/addClient", json_data=payload)
        if resp and resp.get("success"):
            logger.info(f"Created 3x-ui client {cid} email={email}")
            return cid
        logger.error(f"Failed to add 3x-ui client: {resp}")
        return None

    async def update_client(
        self,
        inbound_id: int,
        client_id: str,
        email: str,
        expire_ms: int,
        enable: bool = True,
        sub_id: str = "",
    ) -> bool:
        client_settings = {
            "clients": [{
                "id": client_id,
                "email": email,
                "expiryTime": expire_ms,
                "enable": enable,
                "subId": sub_id,
            }]
        }
        payload = {"id": inbound_id, "settings": client_settings}
        resp = await self._request(
            "POST",
            f"/panel/api/inbounds/updateClient/{client_id}",
            json_data=payload,
        )
        return bool(resp and resp.get("success"))

    async def delete_client(self, inbound_id: int, client_id: str) -> bool:
        resp = await self._request(
            "POST",
            f"/panel/api/inbounds/{inbound_id}/delClient/{client_id}",
        )
        return bool(resp and resp.get("success"))

    async def disable_client(self, inbound_id: int, client_id: str, email: str, sub_id: str = "") -> bool:
        return await self.update_client(
            inbound_id=inbound_id,
            client_id=client_id,
            email=email,
            expire_ms=0,
            enable=False,
            sub_id=sub_id,
        )

    async def get_client_stats(self, email: str) -> Optional[dict]:
        resp = await self._request("GET", f"/panel/api/inbounds/getClientTraffics/{email}")
        if resp and resp.get("success"):
            return resp.get("obj")
        return None

    def build_subscription_url(self, sub_id: str) -> str:
        """Subscription URL по subId клиента: <base>/sub/<subId>"""
        return f"{self.base_url}/sub/{sub_id}"

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


xui_client = XUIClient()
