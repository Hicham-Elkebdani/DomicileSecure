"""In-memory index of known face embeddings.

Matching is a single matrix product, fast for thousands of faces. For a much larger scale,
the same interface can be backed by pgvector or FAISS.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import numpy as np

from app.repositories.person import FaceEmbeddingRepository
from vision.face.similarity import cosine_similarities, vector_from_bytes


@dataclass(frozen=True, slots=True)
class GalleryMatch:
    person_id: uuid.UUID
    score: float


class FaceGallery:
    def __init__(self, threshold: float) -> None:
        self.threshold = threshold
        self._by_model: dict[str, tuple[np.ndarray, list[uuid.UUID]]] = {}
        self._loaded = False
        self._lock = asyncio.Lock()

    async def ensure_loaded(self, repository: FaceEmbeddingRepository) -> None:
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            grouped: dict[str, tuple[list[np.ndarray], list[uuid.UUID]]] = {}
            for row in await repository.list_all():
                vectors, owners = grouped.setdefault(row.model_name, ([], []))
                vectors.append(vector_from_bytes(row.vector))
                owners.append(row.person_id)
            self._by_model = {
                model: (np.vstack(vectors).astype(np.float32), owners)
                for model, (vectors, owners) in grouped.items()
            }
            self._loaded = True

    def invalidate(self) -> None:
        self._loaded = False
        self._by_model = {}

    def add(self, person_id: uuid.UUID, vector: np.ndarray, model_name: str) -> None:
        matrix, owners = self._by_model.get(
            model_name, (np.empty((0, vector.shape[0]), np.float32), [])
        )
        self._by_model[model_name] = (np.vstack([matrix, vector[None, :]]), [*owners, person_id])

    def match(self, vector: np.ndarray, model_name: str) -> GalleryMatch | None:
        entry = self._by_model.get(model_name)
        if entry is None:
            return None
        matrix, owners = entry
        if matrix.shape[1] != vector.shape[0]:
            return None
        scores = cosine_similarities(matrix, vector)
        if scores.size == 0:
            return None
        best = int(np.argmax(scores))
        score = float(scores[best])
        return GalleryMatch(owners[best], score) if score >= self.threshold else None
