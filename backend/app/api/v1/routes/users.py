from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import AdminUser, get_auth_service
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["users"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.get("", response_model=list[UserRead])
async def list_users(_: AdminUser, service: AuthServiceDep) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in await service.list_users()]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, _: AdminUser, service: AuthServiceDep) -> UserRead:
    return UserRead.model_validate(await service.create_user(data))
