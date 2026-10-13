from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from vision.types import FaceEmbedding


class FaceEmbedder(ABC):
    """Detects faces in an image and turns each one into an identity vector."""

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int: ...

    @abstractmethod
    def embed(self, image_bgr: np.ndarray) -> list[FaceEmbedding]:
        """Return one embedding per detected face, largest face first."""
