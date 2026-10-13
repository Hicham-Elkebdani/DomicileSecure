"""ORM models. Importing this package registers every table on `Base.metadata`."""

from app.models.alert import Alert
from app.models.camera import Camera
from app.models.event import Event
from app.models.notification import PushSubscription
from app.models.person import FaceEmbedding, Person
from app.models.summary import DailySummary
from app.models.user import User

__all__ = [
    "Alert",
    "Camera",
    "DailySummary",
    "Event",
    "FaceEmbedding",
    "Person",
    "PushSubscription",
    "User",
]
