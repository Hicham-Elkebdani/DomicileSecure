"""FastAPI dependencies: authentication, sessions and service construction."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import Container
from app.core.config import Settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import api_keys_match, decode_access_token
from app.models import User
from app.repositories.user import UserRepository
from app.services.alert_service import AlertService
from app.services.auth_service import AuthService
from app.services.camera_service import CameraService
from app.services.event_service import EventService
from app.services.ingest_service import IngestService
from app.services.notification_service import NotificationService
from app.services.person_service import PersonService
from app.services.summary_service import SummaryService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_settings_dep(container: ContainerDep) -> Settings:
    return container.settings


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


async def get_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    async with container.database.session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def authenticate_token(token: str, session: AsyncSession, settings: Settings) -> User:
    payload = decode_access_token(
        token,
        secret=settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise AuthenticationError("Jeton d'authentification invalide") from exc
    user = await UserRepository(session).get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Compte introuvable ou désactivé")
    return user


async def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    if not token:
        raise AuthenticationError("Authentification requise")
    return await authenticate_token(token, session, settings)


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise PermissionDeniedError("Droits administrateur requis")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


async def require_worker(
    settings: SettingsDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    if not api_keys_match(x_api_key, settings.worker_api_key.get_secret_value()):
        raise AuthenticationError("Clé API du worker invalide")


# --- Service providers -------------------------------------------------------------------


def get_auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    return AuthService(session, settings)


def get_camera_service(session: SessionDep) -> CameraService:
    return CameraService(session)


def get_person_service(session: SessionDep, container: ContainerDep) -> PersonService:
    return PersonService(session, container.settings, container.gallery)


def get_event_service(session: SessionDep, settings: SettingsDep) -> EventService:
    return EventService(session, settings)


def get_alert_service(session: SessionDep, container: ContainerDep) -> AlertService:
    return AlertService(session, container.settings, container.dispatcher)


def get_summary_service(session: SessionDep, settings: SettingsDep) -> SummaryService:
    return SummaryService(session, settings)


def get_notification_service(session: SessionDep, container: ContainerDep) -> NotificationService:
    return NotificationService(session, container.settings, container.webpush)


def get_ingest_service(
    session: SessionDep,
    container: ContainerDep,
    alert_service: Annotated[AlertService, Depends(get_alert_service)],
) -> IngestService:
    return IngestService(
        session,
        container.settings,
        gallery=container.gallery,
        detector=container.anomaly_detector,
        alert_service=alert_service,
        realtime=container.realtime,
    )
