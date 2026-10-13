from __future__ import annotations

from pydantic import BaseModel, Field


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=255)


class PushSubscriptionCreate(BaseModel):
    """Same shape as the browser's `PushSubscription.toJSON()`."""

    endpoint: str = Field(min_length=10, max_length=2048, pattern=r"^https://")
    keys: PushKeys


class PushSubscriptionDelete(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2048)


class PushConfig(BaseModel):
    enabled: bool
    vapid_public_key: str
