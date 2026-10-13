from fastapi import APIRouter

from app.api.v1.routes import (
    alerts,
    auth,
    cameras,
    events,
    health,
    ingest,
    notifications,
    persons,
    summaries,
    users,
    ws,
)

api_router = APIRouter()
for module in (
    health,
    auth,
    users,
    cameras,
    persons,
    events,
    alerts,
    summaries,
    notifications,
    ingest,
    ws,
):
    api_router.include_router(module.router)
