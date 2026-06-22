from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.user import User
from typing import Optional


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_all(self) -> list[User]:
        result = await self.session.execute(select(User))
        return list(result.scalars().all())

    async def create(
        self,
        user_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> User:
        user = User(id=user_id, username=username, full_name=full_name)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_or_create(
        self,
        user_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> tuple[User, bool]:
        user = await self.get_by_id(user_id)
        if user:
            return user, False
        user = await self.create(user_id, username, full_name)
        return user, True

    async def update(self, user: User) -> User:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def count(self) -> int:
        from sqlalchemy import func
        result = await self.session.execute(select(func.count(User.id)))
        return result.scalar_one()
