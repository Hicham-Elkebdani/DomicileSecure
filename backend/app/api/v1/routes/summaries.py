from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminUser, CurrentUser, get_summary_service
from app.schemas.summary import DailySummaryRead
from app.services.summary_service import SummaryService

router = APIRouter(prefix="/summaries", tags=["summaries"])

SummaryServiceDep = Annotated[SummaryService, Depends(get_summary_service)]


@router.get("", response_model=list[DailySummaryRead], summary="Résumés archivés")
async def list_summaries(
    _: CurrentUser,
    service: SummaryServiceDep,
    limit: Annotated[int, Query(ge=1, le=90)] = 30,
) -> list[DailySummaryRead]:
    return await service.list_recent(limit)


@router.get("/today", response_model=DailySummaryRead, summary="Résumé du jour (temps réel)")
async def today_summary(_: CurrentUser, service: SummaryServiceDep) -> DailySummaryRead:
    return await service.get(service.today())


@router.get("/{day}", response_model=DailySummaryRead)
async def summary_for_day(
    day: date, _: CurrentUser, service: SummaryServiceDep
) -> DailySummaryRead:
    return await service.get(day)


@router.post("/{day}/generate", response_model=DailySummaryRead, summary="(Re)générer un résumé")
async def generate_summary(day: date, _: AdminUser, service: SummaryServiceDep) -> DailySummaryRead:
    return await service.generate(day)
