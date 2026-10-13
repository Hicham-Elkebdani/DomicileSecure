"""Machine-to-machine endpoints used by the vision worker (API-key authentication)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_ingest_service, require_worker
from app.schemas.ingest import IngestResult, ObservationBatch
from app.services.ingest_service import IngestService

router = APIRouter(
    prefix="/ingest", tags=["ingest (worker)"], dependencies=[Depends(require_worker)]
)

IngestServiceDep = Annotated[IngestService, Depends(get_ingest_service)]


@router.post("/observations", response_model=IngestResult)
async def ingest_observations(batch: ObservationBatch, service: IngestServiceDep) -> IngestResult:
    return await service.ingest(batch)


@router.post("/cameras/{camera_id}/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
async def heartbeat(camera_id: uuid.UUID, service: IngestServiceDep) -> Response:
    await service.heartbeat(camera_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
