from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import CurrentUser, get_notification_service
from app.schemas.common import Message
from app.schemas.notification import PushConfig, PushSubscriptionCreate, PushSubscriptionDelete
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])

NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]


@router.get("/config", response_model=PushConfig, summary="Clé publique VAPID")
async def push_config(_: CurrentUser, service: NotificationServiceDep) -> PushConfig:
    return service.config()


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED, response_model=Message)
async def subscribe(
    data: PushSubscriptionCreate,
    request: Request,
    user: CurrentUser,
    service: NotificationServiceDep,
) -> Message:
    await service.subscribe(user, data, request.headers.get("user-agent", ""))
    return Message(message="Notifications activées sur cet appareil")


@router.delete("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    data: PushSubscriptionDelete, user: CurrentUser, service: NotificationServiceDep
) -> Response:
    await service.unsubscribe(user, data.endpoint)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test", response_model=Message, summary="Envoyer une notification de test")
async def send_test(user: CurrentUser, service: NotificationServiceDep) -> Message:
    delivered = await service.send_test(user)
    return Message(message=f"Notification envoyée à {delivered} appareil(s)")
