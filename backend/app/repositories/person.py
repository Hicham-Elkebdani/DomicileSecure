from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select

from app.models import FaceEmbedding, Person
from app.models.enums import PersonRole
from app.repositories.base import BaseRepository


class PersonRepository(BaseRepository[Person]):
    model = Person

    async def list_by_role(self, role: PersonRole | None = None) -> Sequence[Person]:
        query = select(Person).order_by(Person.role, Person.display_name)
        if role is not None:
            query = query.where(Person.role == role)
        return (await self.session.scalars(query)).all()

    async def face_counts(self, person_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not person_ids:
            return {}
        query = (
            select(FaceEmbedding.person_id, func.count(FaceEmbedding.id))
            .where(FaceEmbedding.person_id.in_(person_ids))
            .group_by(FaceEmbedding.person_id)
        )
        return {pid: int(count) for pid, count in (await self.session.execute(query)).all()}

    async def get_many(self, person_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Person]:
        if not person_ids:
            return {}
        rows = await self.session.scalars(select(Person).where(Person.id.in_(person_ids)))
        return {p.id: p for p in rows}


class FaceEmbeddingRepository(BaseRepository[FaceEmbedding]):
    model = FaceEmbedding

    async def list_all(self) -> Sequence[FaceEmbedding]:
        return (await self.session.scalars(select(FaceEmbedding))).all()

    async def delete_for_person(self, person_id: uuid.UUID) -> int:
        result = await self.session.execute(
            delete(FaceEmbedding).where(FaceEmbedding.person_id == person_id)
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def count_for_person(self, person_id: uuid.UUID) -> int:
        query = select(func.count(FaceEmbedding.id)).where(FaceEmbedding.person_id == person_id)
        return int(await self.session.scalar(query) or 0)
