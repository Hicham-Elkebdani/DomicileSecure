"""Shared fixtures.

Tests build the application through the same factory as production, but inject an
in-memory database and a deterministic fake face model (no ONNX files, no camera needed).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import cv2
import httpx
import numpy as np
import pytest
from fastapi import FastAPI

from app.container import Container, build_container
from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from vision.face.base import FaceEmbedder
from vision.face.similarity import l2_normalize
from vision.types import BoundingBox, FaceEmbedding

WORKER_KEY = "test-worker-key"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Admin-Password-123"


class FakeFaceEmbedder(FaceEmbedder):
    """Derives a stable 128-d vector from the dominant colour of the image.

    Two photos of the same solid colour => same identity; different colours => different
    identities. A black image contains "no face"; a half-and-half image contains "two faces".
    """

    @property
    def model_name(self) -> str:
        return "fake-model"

    @property
    def embedding_dim(self) -> int:
        return 128

    @staticmethod
    def vector_for_color(bgr: tuple[int, int, int]) -> np.ndarray:
        rng = np.random.default_rng(abs(hash(bgr)) % (2**32))
        return l2_normalize(rng.normal(size=128))

    def embed(self, image_bgr: np.ndarray) -> list[FaceEmbedding]:
        if image_bgr.max() == 0:
            return []
        height, width = image_bgr.shape[:2]
        halves = [image_bgr[:, : width // 2], image_bgr[:, width // 2 :]]
        colors = {tuple(int(c) for c in half.reshape(-1, 3)[0]) for half in halves}
        return [
            FaceEmbedding(
                bbox=BoundingBox(0, 0, width, height),
                detection_score=0.95,
                vector=self.vector_for_color(color),  # type: ignore[arg-type]
                model_name=self.model_name,
            )
            for color in colors
        ]


def solid_image(bgr: tuple[int, int, int], *, split: tuple[int, int, int] | None = None) -> bytes:
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[:] = bgr
    if split is not None:
        image[:, 32:] = split
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        worker_api_key=WORKER_KEY,
        scheduler_enabled=False,
        timezone="UTC",
        alert_cooldown_minutes=10,
        login_rate_limit_per_minute=5,
        log_level="WARNING",
    )


@pytest.fixture
def fake_embedder() -> FakeFaceEmbedder:
    return FakeFaceEmbedder()


@pytest.fixture
async def container(
    settings: Settings, fake_embedder: FakeFaceEmbedder
) -> AsyncIterator[Container]:
    database = Database(settings.database_url)
    await database.create_all()
    yield build_container(settings, database=database, face_embedder_factory=lambda: fake_embedder)
    await database.dispose()


@pytest.fixture
def app(container: Container) -> FastAPI:
    return create_app(container=container)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c


async def _create_user(container: Container, email: str, password: str, admin: bool) -> None:
    from app.schemas.user import UserCreate
    from app.services.auth_service import AuthService

    async with container.database.session() as session:
        await AuthService(session, container.settings).create_user(
            UserCreate(email=email, password=password, is_admin=admin)
        )


async def _token(client: httpx.AsyncClient, email: str, password: str) -> str:
    response = await client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
async def admin_headers(container: Container, client: httpx.AsyncClient) -> dict[str, str]:
    await _create_user(container, ADMIN_EMAIL, ADMIN_PASSWORD, admin=True)
    return {"Authorization": f"Bearer {await _token(client, ADMIN_EMAIL, ADMIN_PASSWORD)}"}


@pytest.fixture
async def user_headers(container: Container, client: httpx.AsyncClient) -> dict[str, str]:
    await _create_user(container, "member@example.com", "Member-Password-123", admin=False)
    token = await _token(client, "member@example.com", "Member-Password-123")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def worker_headers() -> dict[str, str]:
    return {"X-API-Key": WORKER_KEY}


@pytest.fixture
async def door_camera(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> dict:
    response = await client.post(
        "/cameras",
        json={"name": "Entrée", "location": "Porte d'entrée", "has_door": True},
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def frozen_night() -> datetime:
    """A moment in the night window (23h-6h), always in the past."""
    moment = datetime.now(UTC).replace(hour=2, minute=0, second=0, microsecond=0)
    return moment if moment < datetime.now(UTC) else moment - timedelta(days=1)
