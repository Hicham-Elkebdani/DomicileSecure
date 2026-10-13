"""Turns a face embedding into an identity: resident, guest, visitor or unknown.

Unknown faces are not thrown away: each one becomes an automatic "visitor" profile, so the
next time the same face appears it is recognised as a returning visitor. Once a visitor has
been seen often enough, the household is invited to promote them to guest.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import FaceEmbedding, Person
from app.models.enums import ROLE_TO_IDENTITY, EmbeddingSource, IdentityStatus, PersonRole
from app.repositories.person import FaceEmbeddingRepository, PersonRepository
from app.schemas.ingest import FaceObservation
from app.services.face_gallery import FaceGallery
from vision.face.similarity import l2_normalize, vector_to_bytes


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    identity: IdentityStatus
    person: Person | None
    score: float | None


class IdentityService:
    def __init__(self, session: AsyncSession, settings: Settings, gallery: FaceGallery) -> None:
        self._persons = PersonRepository(session)
        self._embeddings = FaceEmbeddingRepository(session)
        self._settings = settings
        self._gallery = gallery

    async def resolve(
        self, face: FaceObservation | None, observed_at: datetime
    ) -> IdentityResolution:
        if face is None or face.detection_score < self._settings.face_min_detection_score:
            return IdentityResolution(IdentityStatus.UNKNOWN, None, None)

        vector = l2_normalize(face.embedding)
        await self._gallery.ensure_loaded(self._embeddings)
        match = self._gallery.match(vector, face.model_name)

        if match is not None:
            person = await self._persons.get(match.person_id)
            if person is not None:
                self._record_sighting(person, observed_at)
                return IdentityResolution(ROLE_TO_IDENTITY[person.role], person, match.score)
            self._gallery.invalidate()  # stale entry (person deleted meanwhile)

        visitor = await self._create_visitor(vector, face.model_name, observed_at)
        return IdentityResolution(IdentityStatus.UNKNOWN, visitor, None)

    def _record_sighting(self, person: Person, observed_at: datetime) -> None:
        gap = timedelta(minutes=self._settings.sighting_gap_minutes)
        if person.last_seen_at is None or observed_at - person.last_seen_at >= gap:
            person.sightings_count += 1
        if person.first_seen_at is None:
            person.first_seen_at = observed_at
        if person.last_seen_at is None or observed_at > person.last_seen_at:
            person.last_seen_at = observed_at

    async def _create_visitor(
        self, vector: object, model_name: str, observed_at: datetime
    ) -> Person:
        person_id = uuid.uuid4()
        person = Person(
            id=person_id,
            display_name=f"Visiteur {person_id.hex[:6].upper()}",
            role=PersonRole.VISITOR,
            notes="",
            sightings_count=1,
            first_seen_at=observed_at,
            last_seen_at=observed_at,
        )
        self._persons.add(person)
        array = l2_normalize(vector)  # type: ignore[arg-type]
        self._embeddings.add(
            FaceEmbedding(
                person_id=person_id,
                vector=vector_to_bytes(array),
                dim=int(array.shape[0]),
                model_name=model_name,
                source=EmbeddingSource.OBSERVATION,
            )
        )
        await self._persons.flush()
        self._gallery.add(person_id, array, model_name)
        return person
