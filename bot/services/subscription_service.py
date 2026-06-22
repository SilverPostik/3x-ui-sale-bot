import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories import SubscriptionRepository, UserRepository
from bot.services.xui_client import xui_client
from config.settings import settings
from database.models.subscription import Subscription

logger = logging.getLogger(__name__)


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sub_repo = SubscriptionRepository(session)
        self.user_repo = UserRepository(session)

    async def get_active(self, user_id: int) -> Optional[Subscription]:
        return await self.sub_repo.get_active(user_id)

    async def create_subscription(
        self,
        user_id: int,
        plan_months: int,
    ) -> Optional[Subscription]:
        """
        Создаёт нового клиента в 3x-ui и запись в БД.
        sub_id передаётся в 3x-ui — именно он используется в subscription URL.
        """
        expires_at = datetime.now(timezone.utc) + timedelta(days=30 * plan_months)
        expire_ms = int(expires_at.timestamp() * 1000)
        email = f"tg_{user_id}"
        client_id = str(uuid.uuid4())
        sub_id = uuid.uuid4().hex  # subId для subscription URL

        logged_in = await xui_client.login()
        if not logged_in:
            logger.error("Cannot login to 3x-ui")
            return None

        result_id = await xui_client.add_client(
            inbound_id=settings.REALITY_INBOUND_ID,
            email=email,
            expire_ms=expire_ms,
            sub_id=sub_id,
            limit_ip=1,
            total_gb=0,
            client_id=client_id,
        )

        if not result_id:
            logger.error(f"3x-ui add_client failed for user {user_id}")
            return None

        subscription_url = xui_client.build_subscription_url(sub_id)
        logger.info(f"Subscription URL for user {user_id}: {subscription_url}")

        sub = await self.sub_repo.create(
            user_id=user_id,
            plan_months=plan_months,
            expires_at=expires_at,
            xui_client_id=client_id,
            xui_inbound_id=settings.REALITY_INBOUND_ID,
            subscription_url=subscription_url,
            xui_sub_id=sub_id,
            inbound_type="vless_reality",
        )
        return sub

    async def extend_subscription(
        self,
        user_id: int,
        plan_months: int,
    ) -> Optional[Subscription]:
        """
        Продлевает активную подписку или создаёт новую.
        """
        sub = await self.sub_repo.get_active(user_id)
        if sub is None:
            return await self.create_subscription(user_id, plan_months)

        now = datetime.now(timezone.utc)
        base = max(sub.expires_at, now)
        new_expires = base + timedelta(days=30 * plan_months)
        expire_ms = int(new_expires.timestamp() * 1000)
        email = f"tg_{user_id}"

        logged_in = await xui_client.login()
        if not logged_in:
            logger.error("Cannot login to 3x-ui for extend")
            return None

        ok = await xui_client.update_client(
            inbound_id=sub.xui_inbound_id,
            client_id=sub.xui_client_id,
            email=email,
            expire_ms=expire_ms,
            enable=True,
            sub_id=sub.xui_sub_id or "",
        )
        if not ok:
            logger.error(f"3x-ui update_client failed for user {user_id}")
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
        expired = await self.sub_repo.get_expired()
        affected: list[int] = []
        if not expired:
            return affected

        await xui_client.login()
        for sub in expired:
            email = f"tg_{sub.user_id}"
            await xui_client.disable_client(
                inbound_id=sub.xui_inbound_id,
                client_id=sub.xui_client_id,
                email=email,
                sub_id=sub.xui_sub_id or "",
            )
            sub.is_active = False
            await self.sub_repo.update(sub)
            affected.append(sub.user_id)
        return affected
