from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.models import Camera
from app.models.enums import DoorState
from app.repositories.base import BaseRepository


class CameraRepository(BaseRepository[Camera]):
    model = Camera

    async def list_all(self) -> Sequence[Camera]:
        return (await self.session.scalars(select(Camera).order_by(Camera.name))).all()

    async def get_by_name(self, name: str) -> Camera | None:
        return await self.session.scalar(select(Camera).where(Camera.name == name))

    async def list_with_open_door(self) -> Sequence[Camera]:
        query = select(Camera).where(
            Camera.is_active.is_(True),
            Camera.has_door.is_(True),
            Camera.door_state == DoorState.OPEN,
        )
        return (await self.session.scalars(query)).all()
