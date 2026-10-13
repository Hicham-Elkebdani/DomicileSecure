from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import AdminUser, CurrentUser, get_camera_service
from app.schemas.camera import CameraCreate, CameraRead, CameraUpdate
from app.services.camera_service import CameraService

router = APIRouter(prefix="/cameras", tags=["cameras"])

CameraServiceDep = Annotated[CameraService, Depends(get_camera_service)]


@router.get("", response_model=list[CameraRead])
async def list_cameras(_: CurrentUser, service: CameraServiceDep) -> list[CameraRead]:
    return [CameraRead.model_validate(c) for c in await service.list()]


@router.post("", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
async def create_camera(data: CameraCreate, _: AdminUser, service: CameraServiceDep) -> CameraRead:
    return CameraRead.model_validate(await service.create(data))


@router.get("/{camera_id}", response_model=CameraRead)
async def get_camera(camera_id: uuid.UUID, _: CurrentUser, service: CameraServiceDep) -> CameraRead:
    return CameraRead.model_validate(await service.get(camera_id))


@router.patch("/{camera_id}", response_model=CameraRead)
async def update_camera(
    camera_id: uuid.UUID, data: CameraUpdate, _: AdminUser, service: CameraServiceDep
) -> CameraRead:
    return CameraRead.model_validate(await service.update(camera_id, data))


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(camera_id: uuid.UUID, _: AdminUser, service: CameraServiceDep) -> Response:
    await service.delete(camera_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
