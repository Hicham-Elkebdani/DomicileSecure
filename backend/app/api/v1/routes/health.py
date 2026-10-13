from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.api.deps import ContainerDep
from app.core.exceptions import ServiceUnavailableError

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/ready", summary="Readiness probe (database reachable)")
async def readiness(container: ContainerDep) -> dict[str, str]:
    try:
        await container.database.ping()
    except Exception as exc:
        raise ServiceUnavailableError("Base de données indisponible") from exc
    return {
        "status": "ready",
        "anomaly_engine": container.anomaly_detector.name,
        "push": "enabled" if container.webpush else "disabled",
    }
