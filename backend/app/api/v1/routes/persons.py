from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.api.deps import ContainerDep, CurrentUser, get_person_service
from app.core.exceptions import DomainValidationError, PayloadTooLargeError
from app.models.enums import PersonRole
from app.schemas.person import FaceEnrollmentResult, PersonCreate, PersonRead, PersonUpdate
from app.services.person_service import PersonService

router = APIRouter(prefix="/persons", tags=["persons"])

PersonServiceDep = Annotated[PersonService, Depends(get_person_service)]
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.get("", response_model=list[PersonRead])
async def list_persons(
    _: CurrentUser, service: PersonServiceDep, role: PersonRole | None = None
) -> list[PersonRead]:
    return await service.list(role)


@router.post("", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
async def create_person(
    data: PersonCreate, _: CurrentUser, service: PersonServiceDep
) -> PersonRead:
    return await service.create(data)


@router.get("/{person_id}", response_model=PersonRead)
async def get_person(person_id: uuid.UUID, _: CurrentUser, service: PersonServiceDep) -> PersonRead:
    return await service.get(person_id)


@router.patch("/{person_id}", response_model=PersonRead, summary="Renommer / changer le rôle")
async def update_person(
    person_id: uuid.UUID, data: PersonUpdate, _: CurrentUser, service: PersonServiceDep
) -> PersonRead:
    return await service.update(person_id, data)


@router.delete(
    "/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer la personne et ses signatures faciales",
)
async def delete_person(
    person_id: uuid.UUID, _: CurrentUser, service: PersonServiceDep
) -> Response:
    await service.delete(person_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{person_id}/faces",
    response_model=FaceEnrollmentResult,
    status_code=status.HTTP_201_CREATED,
    summary="Enregistrer un visage à partir d'une photo (la photo n'est pas conservée)",
)
async def enroll_face(
    person_id: uuid.UUID,
    _: CurrentUser,
    service: PersonServiceDep,
    container: ContainerDep,
    photo: Annotated[UploadFile, File(description="Photo JPEG/PNG/WebP avec un seul visage")],
) -> FaceEnrollmentResult:
    if photo.content_type not in _ALLOWED_TYPES:
        raise DomainValidationError("Format accepté : JPEG, PNG ou WebP")
    max_bytes = container.settings.max_upload_size_mb * 1024 * 1024
    data = await photo.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise PayloadTooLargeError(
            f"Photo trop lourde (max {container.settings.max_upload_size_mb} Mo)"
        )
    return await service.enroll_face(person_id, data, container.face_embedder.get())


@router.delete(
    "/{person_id}/faces",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer toutes les signatures faciales d'une personne",
)
async def delete_faces(person_id: uuid.UUID, _: CurrentUser, service: PersonServiceDep) -> Response:
    await service.delete_faces(person_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
