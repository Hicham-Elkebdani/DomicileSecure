from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Camera
from app.models.enums import DoorState
from app.repositories.camera import CameraRepository
from app.schemas.camera import CameraCreate, CameraUpdate


class CameraService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cameras = CameraRepository(session)

    async def list(self) -> list[Camera]:
        return list(await self._cameras.list_all())

    async def get(self, camera_id: uuid.UUID) -> Camera:
        camera = await self._cameras.get(camera_id)
        if camera is None:
            raise NotFoundError("Caméra introuvable")
        return camera

    async def create(self, data: CameraCreate) -> Camera:
        if await self._cameras.get_by_name(data.name):
            raise ConflictError("Une caméra porte déjà ce nom")
        camera = Camera(**data.model_dump(), door_state=DoorState.UNKNOWN)
        self._cameras.add(camera)
        await self._session.commit()
        return camera

    async def update(self, camera_id: uuid.UUID, data: CameraUpdate) -> Camera:
        camera = await self.get(camera_id)
        changes = data.model_dump(exclude_unset=True)
        new_name = changes.get("name")
        if new_name and new_name != camera.name and await self._cameras.get_by_name(new_name):
            raise ConflictError("Une caméra porte déjà ce nom")
        for field, value in changes.items():
            setattr(camera, field, value)
        if changes.get("has_door") is False:
            camera.door_state = DoorState.UNKNOWN
            camera.door_state_changed_at = None
        await self._session.commit()
        return camera

    async def delete(self, camera_id: uuid.UUID) -> None:
        camera = await self.get(camera_id)
        await self._cameras.delete(camera)
        await self._session.commit()
