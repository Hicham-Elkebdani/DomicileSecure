from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.models import PushSubscription, User
from app.repositories.notification import PushSubscriptionRepository
from app.schemas.notification import PushConfig, PushSubscriptionCreate
from app.services.notifications.webpush import WebPushChannel


class NotificationService:
    def __init__(
        self, session: AsyncSession, settings: Settings, webpush: WebPushChannel | None
    ) -> None:
        self._session = session
        self._subscriptions = PushSubscriptionRepository(session)
        self._settings = settings
        self._webpush = webpush

    def config(self) -> PushConfig:
        return PushConfig(
            enabled=self._settings.push_enabled, vapid_public_key=self._settings.vapid_public_key
        )

    async def subscribe(
        self, user: User, data: PushSubscriptionCreate, user_agent: str
    ) -> PushSubscription:
        subscription = await self._subscriptions.get_by_endpoint(data.endpoint)
        if subscription is None:
            subscription = PushSubscription(endpoint=data.endpoint)
            self._subscriptions.add(subscription)
        subscription.user_id = user.id
        subscription.p256dh = data.keys.p256dh
        subscription.auth = data.keys.auth
        subscription.user_agent = user_agent[:255]
        await self._session.commit()
        return subscription

    async def unsubscribe(self, user: User, endpoint: str) -> None:
        subscription = await self._subscriptions.get_by_endpoint(endpoint)
        if subscription is None or subscription.user_id != user.id:
            raise NotFoundError("Abonnement introuvable")
        await self._subscriptions.delete(subscription)
        await self._session.commit()

    async def send_test(self, user: User) -> int:
        if self._webpush is None or not self._settings.push_enabled:
            raise ServiceUnavailableError("Les notifications push ne sont pas configurées")
        subscriptions = list(await self._subscriptions.list_for_user(user.id))
        if not subscriptions:
            raise NotFoundError("Aucun appareil abonné pour ce compte")
        payload = {
            "title": "DomicileSecure",
            "body": "Notification de test : tout fonctionne !",
            "url": "/",
            "tag": "test",
        }
        expired = await self._webpush.send_to_subscriptions(subscriptions, payload)
        if expired:
            await self._subscriptions.delete_by_endpoints(expired)
            await self._session.commit()
        return len(subscriptions) - len(expired)
