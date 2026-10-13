from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    def expand(self, ratio: float, max_width: int, max_height: int) -> BoundingBox:
        dx, dy = self.width * ratio, self.height * ratio
        return BoundingBox(
            max(0.0, self.x1 - dx),
            max(0.0, self.y1 - dy),
            min(float(max_width), self.x2 + dx),
            min(float(max_height), self.y2 + dy),
        )

    def as_int_tuple(self) -> tuple[int, int, int, int]:
        return int(self.x1), int(self.y1), int(self.x2), int(self.y2)

    def as_list(self) -> list[float]:
        return [round(self.x1, 1), round(self.y1, 1), round(self.x2, 1), round(self.y2, 1)]


@dataclass(frozen=True, slots=True)
class Detection:
    label: str
    confidence: float
    bbox: BoundingBox
    track_id: int | None = None


@dataclass(frozen=True, slots=True)
class FaceEmbedding:
    bbox: BoundingBox
    detection_score: float
    vector: np.ndarray  # L2-normalised float32
    model_name: str
