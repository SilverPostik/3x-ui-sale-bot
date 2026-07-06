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

    async def create_subscription(
        self,
        user_id: int,
        plan_months: int,
    ) -> Optional[Subscription]:
        """
        Создаёт нового клиента в 3x-ui и запись в БД.
        """
        expires_at = datetime.now(timezone.utc) + timedelta(days=30 * plan_months)
        expire_ms = int(expires_at.timestamp() * 1000)

        # email должен быть уникальным в рамках inbound
        email = f"tg{user_id}"
        client_id = str(uuid.uuid4())
        # subId явно передаём — 3x-ui не генерирует его сам через API (issue #3237)
        sub_id = uuid.uuid4().hex[:16]

        logger.info(
            f"Creating 3x-ui client: user={user_id} email={email} "
            f"sub_id={sub_id} expire={expires_at.isoformat()}"
        )

        result_id = await xui_client.add_client(
            inbound_ids=settings.INBOUND_IDS,
            email=email,
            expire_ms=expire_ms,
            sub_id=sub_id,
            client_id=client_id,
            limit_ip=settings.DEFAULT_LIMIT_IP,
            total_gb=0,
            flow="xtls-rprx-vision",
        )

        if not result_id:
            logger.error(f"Failed to create 3x-ui client for user {user_id}")
            return None

        subscription_url = xui_client.build_subscription_url(sub_id)
        logger.info(f"Subscription URL for user {user_id}: {subscription_url}")

        sub = await self.sub_repo.create(
            user_id=user_id,
            plan_months=plan_months,
            expires_at=expires_at,
            xui_client_id=client_id,
            xui_inbound_ids=settings.INBOUND_IDS,
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

        logger.info(
            f"Creating 3x-ui promo client: user={user_id} email={email} "
            f"sub_id={sub_id} expire={expires_at.isoformat()}"
        )

        result_id = await xui_client.add_client(
            inbound_ids=settings.INBOUND_IDS,
            email=email,
            expire_ms=expire_ms,
            sub_id=sub_id,
            client_id=client_id,
            limit_ip=settings.DEFAULT_LIMIT_IP,
            total_gb=0,
            flow="xtls-rprx-vision",
        )

        if not result_id:
            logger.error(f"Failed to create promo 3x-ui client for user {user_id}")
            return None

        subscription_url = xui_client.build_subscription_url(sub_id)
        logger.info(f"Promo subscription URL for user {user_id}: {subscription_url}")

        sub = await self.sub_repo.create(
            user_id=user_id,
            plan_months=0,
            expires_at=expires_at,
            xui_client_id=client_id,
            xui_inbound_ids=settings.INBOUND_IDS,
            xui_sub_id=sub_id,
            subscription_url=subscription_url,
            inbound_type="vless_reality",
        )
        return sub

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
        email = f"tg{user_id}"

        logger.info(
            f"Extending 3x-ui client: user={user_id} client_id={sub.xui_client_id} "
            f"new_expires={new_expires.isoformat()}"
        )

        ok = await xui_client.update_client(
            inbound_ids=sub.inbound_id_list or settings.INBOUND_IDS,
            client_id=sub.xui_client_id,
            email=email,
            expire_ms=expire_ms,
            sub_id=sub.xui_sub_id or "",
            enable=True,
            flow="xtls-rprx-vision",
        )

        if not ok:
            logger.error(f"3x-ui updateClient failed for user {user_id}")
            return None

        sub.expires_at = new_expires
        sub.plan_months = plan_months
        sub.is_active = True
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
            email = f"tg{sub.user_id}"
            ok = await xui_client.disable_client(
                inbound_ids=sub.inbound_id_list or settings.INBOUND_IDS,
                client_id=sub.xui_client_id,
                email=email,
                sub_id=sub.xui_sub_id or "",
            )
            if ok:
                logger.info(f"Disabled 3x-ui client for user {sub.user_id}")
            else:
                logger.warning(f"Failed to disable 3x-ui client for user {sub.user_id}")
            sub.is_active = False
            await self.sub_repo.update(sub)
            affected.append(sub.user_id)
        return affected
