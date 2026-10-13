from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import ContainerDep, CurrentUser, get_auth_service
from app.core.exceptions import RateLimitedError
from app.schemas.user import Token, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token, summary="Obtenir un jeton d'accès (JWT)")
async def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    container: ContainerDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Token:
    client_ip = request.client.host if request.client else "unknown"
    if not await container.login_limiter.hit(f"login:{client_ip}"):
        raise RateLimitedError("Trop de tentatives, réessayez dans une minute")
    token = await service.authenticate(form.username, form.password)
    await container.login_limiter.reset(f"login:{client_ip}")
    return token


@router.get("/me", response_model=UserRead, summary="Utilisateur connecté")
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
