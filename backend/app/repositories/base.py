"""Generic repository: the only layer that builds SQL queries.

Services depend on repositories, never on SQLAlchemy queries directly, which keeps business
logic testable and lets the storage evolve (e.g. pgvector for embeddings) in one place.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)

    async def flush(self) -> None:
        await self.session.flush()

    async def paginate(
        self, query: Select[Any], *, limit: int, offset: int
    ) -> tuple[Sequence[ModelT], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        rows = await self.session.scalars(query.limit(limit).offset(offset))
        return rows.all(), int(total or 0)
