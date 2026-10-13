from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(
            select(User).where(func.lower(User.email) == email.lower())
        )

    async def list_all(self) -> Sequence[User]:
        return (await self.session.scalars(select(User).order_by(User.created_at))).all()

    async def count(self) -> int:
        return int(await self.session.scalar(select(func.count(User.id))) or 0)
