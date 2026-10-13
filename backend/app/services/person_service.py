from __future__ import annotations

import uuid

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import DomainValidationError, NotFoundError
from app.models import FaceEmbedding, Person
from app.models.enums import EmbeddingSource, PersonRole
from app.repositories.person import FaceEmbeddingRepository, PersonRepository
from app.schemas.person import FaceEnrollmentResult, PersonCreate, PersonRead, PersonUpdate
from app.services.face_gallery import FaceGallery
from vision.face.base import FaceEmbedder
from vision.face.similarity import vector_to_bytes
from vision.image import decode_image
from vision.types import FaceEmbedding as DetectedFace


class PersonService:
    def __init__(self, session: AsyncSession, settings: Settings, gallery: FaceGallery) -> None:
        self._session = session
        self._persons = PersonRepository(session)
        self._embeddings = FaceEmbeddingRepository(session)
        self._settings = settings
        self._gallery = gallery

    async def list(self, role: PersonRole | None = None) -> list[PersonRead]:
        persons = list(await self._persons.list_by_role(role))
        counts = await self._persons.face_counts([p.id for p in persons])
        return [self._to_read(p, counts.get(p.id, 0)) for p in persons]

    async def get(self, person_id: uuid.UUID) -> PersonRead:
        person = await self._get(person_id)
        return self._to_read(person, await self._embeddings.count_for_person(person.id))

    async def create(self, data: PersonCreate) -> PersonRead:
        person = Person(
            display_name=data.display_name, role=data.role, notes=data.notes, sightings_count=0
        )
        self._persons.add(person)
        await self._session.commit()
        return self._to_read(person, 0)

    async def update(self, person_id: uuid.UUID, data: PersonUpdate) -> PersonRead:
        person = await self._get(person_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(person, field, value)
        await self._session.commit()
        self._gallery.invalidate()
        return self._to_read(person, await self._embeddings.count_for_person(person.id))

    async def delete(self, person_id: uuid.UUID) -> None:
        """Deletes the person and all their face signatures (right to erasure)."""
        person = await self._get(person_id)
        await self._persons.delete(person)
        await self._session.commit()
        self._gallery.invalidate()

    async def delete_faces(self, person_id: uuid.UUID) -> None:
        await self._get(person_id)
        await self._embeddings.delete_for_person(person_id)
        await self._session.commit()
        self._gallery.invalidate()

    async def enroll_face(
        self, person_id: uuid.UUID, image_bytes: bytes, embedder: FaceEmbedder
    ) -> FaceEnrollmentResult:
        person = await self._get(person_id)
        face = await run_in_threadpool(self._extract_single_face, image_bytes, embedder)

        embedding = FaceEmbedding(
            person_id=person.id,
            vector=vector_to_bytes(face.vector),
            dim=int(face.vector.shape[0]),
            model_name=face.model_name,
            source=EmbeddingSource.ENROLLMENT,
        )
        self._embeddings.add(embedding)
        await self._session.commit()
        self._gallery.invalidate()
        return FaceEnrollmentResult(
            person_id=person.id,
            embedding_id=embedding.id,
            face_count=await self._embeddings.count_for_person(person.id),
            detection_score=round(face.detection_score, 3),
        )

    def _extract_single_face(self, image_bytes: bytes, embedder: FaceEmbedder) -> DetectedFace:
        try:
            image = decode_image(image_bytes)
        except ValueError as exc:
            raise DomainValidationError("Image illisible ou format non supporté") from exc
        faces = embedder.embed(image)
        if not faces:
            raise DomainValidationError("Aucun visage détecté sur la photo")
        if len(faces) > 1:
            raise DomainValidationError(
                "Plusieurs visages détectés : utilisez une photo avec une seule personne",
                details={"faces": len(faces)},
            )
        face = faces[0]
        if face.detection_score < self._settings.face_min_detection_score:
            raise DomainValidationError(
                "Visage trop flou ou trop petit, utilisez une photo plus nette",
                details={"detection_score": round(face.detection_score, 3)},
            )
        return face

    async def _get(self, person_id: uuid.UUID) -> Person:
        person = await self._persons.get(person_id)
        if person is None:
            raise NotFoundError("Personne introuvable")
        return person

    def _to_read(self, person: Person, face_count: int) -> PersonRead:
        read = PersonRead.model_validate(person)
        read.face_count = face_count
        read.is_recurring = (
            person.role is PersonRole.VISITOR
            and person.sightings_count >= self._settings.recurring_visitor_threshold
        )
        return read
