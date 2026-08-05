import asyncio
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import SubscriptionRepository
from bot.services.xui_client import xui_client
from config.settings import settings
from database.models.subscription import Subscription

logger = logging.getLogger(__name__)


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sub_repo = SubscriptionRepository(session)

    async def get_active(self, user_id: int) -> Optional[Subscription]:
        return await self.sub_repo.get_active(user_id)

    async def sync_from_panel_if_missing(self, user_id: int) -> Optional[Subscription]:
        """
        Самовосстановление: если у пользователя нет НИ ОДНОЙ записи подписки в БД,
        но в панели 3x-ui реально есть его клиент (email "tg<user_id>") — значит
        данные когда-то потерялись (например, после сбоя БД, если для этого
        конкретного пользователя не прогнали scripts/recover_from_panel.py).
        В этом случае восстанавливаем запись прямо здесь, при обращении
        пользователя к боту — так же, как это делает recover_from_panel.py,
        но точечно для одного человека и без ручного вмешательства админа.

        Возвращает восстановленную подписку, либо None если восстанавливать
        нечего (запись в БД уже есть, либо клиента нет и в панели).
        """
        existing = await self.sub_repo.get_last(user_id)
        if existing is not None:
            return None  # нечего восстанавливать — запись уже есть

        email = f"tg{user_id}"
        details = await xui_client.find_client_details_by_email(email)
        if not details:
            return None  # пользователя нет и в панели — это просто новый юзер

        expiry_ms = details.get("expiryTime", 0)
        now = datetime.now(timezone.utc)
        if expiry_ms and expiry_ms > 0:
            expires_at = datetime.fromtimestamp(expiry_ms / 1000, tz=timezone.utc)
        else:
            expires_at = now.replace(year=now.year + 5)
            logger.warning(f"sync_from_panel: user={user_id} expiryTime=0 (без срока), ставлю +5 лет")

        is_active = bool(details.get("enable", True)) and expires_at > now
        inbound_ids = details.get("inbound_ids") or []
        sub_id = details.get("subId", "")
        sub_url = xui_client.build_subscription_url(sub_id) if sub_id else None

        logger.info(
            f"sync_from_panel: восстанавливаю подписку для user={user_id} "
            f"(expires_at={expires_at.isoformat()}, inbounds={inbound_ids}) — "
            f"клиент найден в панели, но отсутствовал в БД"
        )

        sub = await self.sub_repo.create(
            user_id=user_id,
            plan_months=0,  # неизвестно, в панели этой информации нет
            expires_at=expires_at,
            xui_client_id=details.get("id", ""),
            xui_inbound_id=Subscription.format_inbound_ids(inbound_ids),
            xui_sub_id=sub_id,
            subscription_url=sub_url,
            devices=details.get("limitIp") or 1,
            inbound_type="vless_reality",
        )
        sub.is_active = is_active
        sub = await self.sub_repo.update(sub)
        return sub

    async def has_capacity_for_new_user(self, user_id: int) -> bool:
        """
        Проверяет, можно ли создать НОВУЮ подписку с учётом MAX_ACTIVE_SUBSCRIPTIONS.
        0 — лимит не задан (без ограничений).
        Продление уже существующей у пользователя подписки лимитом не блокируется —
        проверка актуальна только для тех, у кого ещё нет ни одной записи подписки.
        """
        if settings.MAX_ACTIVE_SUBSCRIPTIONS <= 0:
            return True
        existing = await self.sub_repo.get_last(user_id)
        if existing is not None:
            return True
        active_count = await self.sub_repo.count_active()
        return active_count < settings.MAX_ACTIVE_SUBSCRIPTIONS

    async def _add_client_with_retries(
        self,
        inbound_ids: list[int],
        email: str,
        expire_ms: int,
        sub_id: str,
        client_id: str,
        retries: int = 3,
        delay: float = 3.0,
    ) -> Optional[str]:
        """
        xui_client.add_client уже ретраит пустые ответы и откатывает частичный
        успех внутри одного вызова, но добавляем внешний уровень попыток —
        на случай, если сама панель в моммент вызова временно недоступна целиком.
        """
        for attempt in range(1, retries + 1):
            result_id = await xui_client.add_client(
                inbound_ids=inbound_ids,
                email=email,
                expire_ms=expire_ms,
                sub_id=sub_id,
                client_id=client_id,
                limit_ip=settings.DEFAULT_LIMIT_IP,
                total_gb=0,
                flow="xtls-rprx-vision",
            )
            if result_id:
                return result_id
            logger.warning(f"3x-ui add_client попытка {attempt}/{retries} неудачна для email={email}")
            if attempt < retries:
                await asyncio.sleep(delay)
        return None

    async def create_subscription(
        self,
        user_id: int,
        plan_months: int,
    ) -> Optional[Subscription]:
        """
        Создаёт нового клиента в 3x-ui и запись в БД.
        Клиент создаётся сразу во всех inbound'ах из settings.REALITY_INBOUND_ID.
        """
        if not await self.has_capacity_for_new_user(user_id):
            logger.warning(
                f"MAX_ACTIVE_SUBSCRIPTIONS limit reached, rejecting new subscription for user {user_id}"
            )
            return None

        expires_at = datetime.now(timezone.utc) + timedelta(days=30 * plan_months)
        expire_ms = int(expires_at.timestamp() * 1000)

        # email должен быть уникальным в рамках inbound
        email = f"tg{user_id}"
        client_id = str(uuid.uuid4())
        # subId явно передаём — 3x-ui не генерирует его сам через API (issue #3237)
        sub_id = uuid.uuid4().hex[:16]
        inbound_ids = settings.REALITY_INBOUND_ID

        logger.info(
            f"Creating 3x-ui client: user={user_id} email={email} "
            f"sub_id={sub_id} expire={expires_at.isoformat()} inbounds={inbound_ids}"
        )

        result_id = await self._add_client_with_retries(
            inbound_ids=inbound_ids,
            email=email,
            expire_ms=expire_ms,
            sub_id=sub_id,
            client_id=client_id,
        )

        if not result_id:
            logger.error(f"Failed to create 3x-ui client for user {user_id} (все попытки исчерпаны)")
            return None

        subscription_url = xui_client.build_subscription_url(sub_id)
        logger.info(f"Subscription URL for user {user_id}: {subscription_url}")

        sub = await self.sub_repo.create(
            user_id=user_id,
            plan_months=plan_months,
            expires_at=expires_at,
            xui_client_id=client_id,
            xui_inbound_id=Subscription.format_inbound_ids(inbound_ids),
            xui_sub_id=sub_id,
            subscription_url=subscription_url,
            inbound_type="vless_reality",
        )
        return sub

    async def create_promo_subscription(
        self,
        user_id: int,
        days: int,
    ) -> Optional[Subscription]:
        """
        Создаёт нового клиента в 3x-ui для промокода на дни.
        """
        expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        expire_ms = int(expires_at.timestamp() * 1000)

        email = f"tg{user_id}"
        client_id = str(uuid.uuid4())
        sub_id = uuid.uuid4().hex[:16]
        inbound_ids = settings.REALITY_INBOUND_ID

        logger.info(
            f"Creating 3x-ui promo client: user={user_id} email={email} "
            f"sub_id={sub_id} expire={expires_at.isoformat()} inbounds={inbound_ids}"
        )

        result_id = await self._add_client_with_retries(
            inbound_ids=inbound_ids,
            email=email,
            expire_ms=expire_ms,
            sub_id=sub_id,
            client_id=client_id,
        )

        if not result_id:
            logger.error(f"Failed to create promo 3x-ui client for user {user_id} (все попытки исчерпаны)")
            return None

        subscription_url = xui_client.build_subscription_url(sub_id)
        logger.info(f"Promo subscription URL for user {user_id}: {subscription_url}")

        sub = await self.sub_repo.create(
            user_id=user_id,
            plan_months=0,
            expires_at=expires_at,
            xui_client_id=client_id,
            xui_inbound_id=Subscription.format_inbound_ids(inbound_ids),
            xui_sub_id=sub_id,
            subscription_url=subscription_url,
            inbound_type="vless_reality",
        )
        return sub

    async def _sync_client_with_retries(
        self,
        sub: Subscription,
        expire_ms: int,
        enable: bool,
        retries: int = 3,
        delay: float = 3.0,
    ) -> bool:
        """
        Синхронизирует expire/enable клиента в 3x-ui. xui_client.update_client уже
        ретраит пустые ответы панели внутри одного вызова, но здесь добавлен ещё
        один, более "длинный" уровень попыток — на случай, если сама панель на
        момент вызова временно недоступна целиком (перезагрузка, сеть и т.п.),
        а не просто отдаёт пустой ответ на один конкретный запрос.
        """
        email = f"tg{sub.user_id}"
        for attempt in range(1, retries + 1):
            ok = await xui_client.update_client(
                inbound_ids=sub.inbound_ids,
                client_id=sub.xui_client_id,
                email=email,
                expire_ms=expire_ms,
                sub_id=sub.xui_sub_id or "",
                enable=enable,
                flow="xtls-rprx-vision",
            )
            if ok:
                return True
            logger.warning(
                f"3x-ui update_client попытка {attempt}/{retries} неудачна для user={sub.user_id}"
            )
            if attempt < retries:
                await asyncio.sleep(delay)
        return False

    async def extend_subscription(
        self,
        user_id: int,
        plan_months: int,
    ) -> Optional[Subscription]:
        """
        Продлевает активную подписку. Если нет — создаёт новую.
        """
        sub = await self.sub_repo.get_active(user_id)
        if sub is None:
            # Проверяем — вдруг истекшая подписка уже есть (нужно продлить её же)
            sub = await self.sub_repo.get_last(user_id)

        if sub is None:
            return await self.create_subscription(user_id, plan_months)

        now = datetime.now(timezone.utc)
        base = sub.expires_at if sub.expires_at.tzinfo else sub.expires_at.replace(tzinfo=timezone.utc)
        new_expires = max(base, now) + timedelta(days=30 * plan_months)
        expire_ms = int(new_expires.timestamp() * 1000)

        logger.info(
            f"Extending 3x-ui client: user={user_id} client_id={sub.xui_client_id} "
            f"new_expires={new_expires.isoformat()}"
        )

        ok = await self._sync_client_with_retries(sub, expire_ms, enable=True)

        if not ok:
            logger.error(f"3x-ui updateClient failed for user {user_id} (все попытки исчерпаны)")
            return None

        sub.expires_at = new_expires
        sub.plan_months = plan_months
        sub.is_active = True
        sub.notified_7d = False
        sub.notified_3d = False
        sub.notified_1d = False
        sub = await self.sub_repo.update(sub)
        return sub

    # ------------------------------------------------------------------ admin

    async def admin_adjust_expiry(self, user_id: int, delta_days: int) -> Optional[Subscription]:
        """
        Ручная корректировка админом: +/- дней к текущему сроку подписки.
        Если подписки ещё нет вообще и delta_days > 0 — создаёт новую (как промо).
        Синхронизирует 3x-ui и БД, всегда меняются оба места вместе.
        """
        sub = await self.sub_repo.get_last(user_id)
        now = datetime.now(timezone.utc)

        if sub is None:
            if delta_days <= 0:
                return None
            return await self.create_promo_subscription(user_id, delta_days)

        base = sub.expires_at if sub.expires_at.tzinfo else sub.expires_at.replace(tzinfo=timezone.utc)
        new_expires = max(base, now) + timedelta(days=delta_days)
        return await self._apply_admin_change(sub, new_expires, enable=True)

    async def admin_set_expiry_date(self, user_id: int, new_date: datetime) -> Optional[Subscription]:
        """Устанавливает точную дату окончания подписки (не относительно текущей)."""
        sub = await self.sub_repo.get_last(user_id)
        if sub is None:
            return None
        if new_date.tzinfo is None:
            new_date = new_date.replace(tzinfo=timezone.utc)
        enable = new_date > datetime.now(timezone.utc)
        return await self._apply_admin_change(sub, new_date, enable=enable)

    async def admin_set_active(self, user_id: int, enable: bool) -> Optional[Subscription]:
        """Принудительно включает/отключает клиента в 3x-ui, не трогая срок действия."""
        sub = await self.sub_repo.get_last(user_id)
        if sub is None:
            return None
        return await self._apply_admin_change(sub, sub.expires_at, enable=enable)

    async def _apply_admin_change(
        self,
        sub: Subscription,
        new_expires_at: datetime,
        enable: bool,
    ) -> Optional[Subscription]:
        if new_expires_at.tzinfo is None:
            new_expires_at = new_expires_at.replace(tzinfo=timezone.utc)
        expire_ms = int(new_expires_at.timestamp() * 1000)

        ok = await self._sync_client_with_retries(sub, expire_ms, enable=enable)
        if not ok:
            logger.error(f"admin change: 3x-ui sync failed for user={sub.user_id} (все попытки исчерпаны)")
            return None

        sub.expires_at = new_expires_at
        sub.is_active = enable and new_expires_at > datetime.now(timezone.utc)
        sub.notified_7d = False
        sub.notified_3d = False
        sub.notified_1d = False
        sub = await self.sub_repo.update(sub)
        return sub

    async def disable_expired(self) -> list[int]:
        """Отключает истёкшие подписки в 3x-ui и БД."""
        expired = await self.sub_repo.get_expired()
        affected: list[int] = []
        for sub in expired:
            expire_ms = int(sub.expires_at.timestamp() * 1000)
            ok = await self._sync_client_with_retries(sub, expire_ms, enable=False)
            if ok:
                logger.info(f"Disabled 3x-ui client for user {sub.user_id}")
            else:
                logger.warning(f"Failed to disable 3x-ui client for user {sub.user_id} (все попытки исчерпаны)")
            sub.is_active = False
            await self.sub_repo.update(sub)
            affected.append(sub.user_id)
        return affected
