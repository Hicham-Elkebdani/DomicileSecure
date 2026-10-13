from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_alert_service
from app.models.enums import AlertSeverity, AlertStatus
from app.schemas.alert import AlertCounts, AlertRead, AlertUpdate
from app.schemas.common import Page
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])

AlertServiceDep = Annotated[AlertService, Depends(get_alert_service)]


@router.get("", response_model=Page[AlertRead])
async def list_alerts(
    _: CurrentUser,
    service: AlertServiceDep,
    status: AlertStatus | None = None,
    min_severity: AlertSeverity | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AlertRead]:
    return await service.list(
        status=status,
        min_severity=min_severity,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )


@router.get("/counts", response_model=AlertCounts, summary="Nombre d'alertes non traitées")
async def alert_counts(_: CurrentUser, service: AlertServiceDep) -> AlertCounts:
    return await service.counts()


@router.patch(
    "/{alert_id}",
    response_model=AlertRead,
    summary="Marquer comme traitée ou comme fausse alerte",
)
async def update_alert(
    alert_id: uuid.UUID, data: AlertUpdate, user: CurrentUser, service: AlertServiceDep
) -> AlertRead:
    return AlertRead.model_validate(await service.update_status(alert_id, data.status, user))
