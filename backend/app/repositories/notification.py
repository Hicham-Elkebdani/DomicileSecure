from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select

from app.models import PushSubscription
from app.repositories.base import BaseRepository


class PushSubscriptionRepository(BaseRepository[PushSubscription]):
    model = PushSubscription

    async def get_by_endpoint(self, endpoint: str) -> PushSubscription | None:
        return await self.session.scalar(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )

    async def list_all(self) -> Sequence[PushSubscription]:
        return (await self.session.scalars(select(PushSubscription))).all()

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[PushSubscription]:
        query = select(PushSubscription).where(PushSubscription.user_id == user_id)
        return (await self.session.scalars(query)).all()

    async def delete_by_endpoints(self, endpoints: Sequence[str]) -> None:
        if endpoints:
            await self.session.execute(
                delete(PushSubscription).where(PushSubscription.endpoint.in_(endpoints))
            )
