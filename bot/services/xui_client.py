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

    async def login(self) -> bool:
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/login",
                data={"username": self.username, "password": self.password},
                ssl=False,
            ) as resp:
                data = await resp.json(content_type=None)
                success = data.get("success", False)
                if success:
                    logger.info("3x-ui login successful")
                else:
                    logger.error(f"3x-ui login failed: {data}")
                return success
        except Exception as e:
            logger.error(f"3x-ui login exception: {e}")
            return False

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict] = None,
        retry: bool = True,
    ) -> Optional[dict]:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        try:
            async with session.request(
                method, url, json=json_data, ssl=False
            ) as resp:
                if resp.status == 401 and retry:
                    logged_in = await self.login()
                    if logged_in:
                        return await self._request(method, path, json_data, retry=False)
                    return None
                data = await resp.json(content_type=None)
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
        # ВАЖНО: settings передаётся как JSON-строка (требование 3x-ui API)
        client_settings = json.dumps({
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
        })
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
        client_settings = json.dumps({
            "clients": [{
                "id": client_id,
                "email": email,
                "expiryTime": expire_ms,
                "enable": enable,
                "subId": sub_id,
            }]
        })
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
