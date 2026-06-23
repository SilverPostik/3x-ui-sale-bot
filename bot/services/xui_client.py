"""
3x-ui API client — обновлен для безопасной работы с base path.
"""
import asyncio
import json
import logging
import uuid
from typing import Optional
from urllib.parse import urljoin

import aiohttp
from config.settings import settings

logger = logging.getLogger(__name__)

_RETRY_COUNT = 3
_RETRY_DELAY = 1.0  # seconds


class XUIClient:
    def __init__(self) -> None:
        # Гарантируем, что базовый URL всегда заканчивается на слэш
        base = settings.THREEXUI_URL.strip()
        if not base.endswith("/"):
            base += "/"
        self._base = base
        
        self._username = settings.THREEXUI_USERNAME
        self._password = settings.THREEXUI_PASSWORD
        self._session: Optional[aiohttp.ClientSession] = None
        self._logged_in: bool = False

    # ------------------------------------------------------------------ session

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
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
        session = await self._get_session()
        # urljoin правильно склеит базовый путь и login
        url = urljoin(self._base, "login")
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
        await self._ensure_login()
        session = await self._get_session()
        
        # Убираем начальный слэш у пути, если он есть, чтобы urljoin сработал верно
        clean_path = path.lstrip("/")
        url = urljoin(self._base, clean_path)

        for attempt in range(1, _RETRY_COUNT + 1):
            try:
                async with session.request(
                    method,
                    url,
                    json=json_body,
                    headers={"Accept": "application/json"},
                ) as resp:
                    text = await resp.text()

                    if not text.strip():
                        logger.warning(
                            f"3x-ui empty response [{attempt}/{_RETRY_COUNT}] "
                            f"{method} {path}"
                        )
                        if attempt < _RETRY_COUNT:
                            await asyncio.sleep(_RETRY_DELAY)
                            continue
                        return None

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
        resp = await self._request("GET", "panel/api/inbounds/list")
        if resp and resp.get("success"):
            return resp.get("obj") or []
        return []

    async def get_inbound(self, inbound_id: int) -> Optional[dict]:
        resp = await self._request("GET", f"panel/api/inbounds/get/{inbound_id}")
        if resp and resp.get("success"):
            return resp.get("obj")
        return None

    # ------------------------------------------------------------------ clients

    def _make_client_settings_str(self, clients: list[dict]) -> str:
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
        resp = await self._request("POST", "panel/api/inbounds/addClient", json_body=payload)
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
            f"panel/api/inbounds/updateClient/{client_id}",
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
            f"panel/api/inbounds/{inbound_id}/delClient/{client_id}",
        )
        return bool(resp and resp.get("success"))

    async def get_client_stats(self, email: str) -> Optional[dict]:
        resp = await self._request(
            "GET", f"panel/api/inbounds/getClientTraffics/{email}"
        )
        if resp and resp.get("success"):
            return resp.get("obj")
        return None

    async def online_clients(self) -> list[str]:
        resp = await self._request("POST", "panel/api/inbounds/onlines")
        if resp and resp.get("success"):
            return resp.get("obj") or []
        return []

    # ------------------------------------------------------------------ subscription URL

    def build_subscription_url(self, sub_id: str) -> str:
        return urljoin(self._base, f"sub/{sub_id}")

    # ------------------------------------------------------------------ diagnostics

    async def ping(self) -> bool:
        inbounds = await self.get_inbounds()
        return isinstance(inbounds, list)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

# Глобальный singleton
xui_client = XUIClient()