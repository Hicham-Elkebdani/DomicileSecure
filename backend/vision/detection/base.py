from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from vision.types import Detection


class ObjectDetector(ABC):
    @abstractmethod
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        """Detect objects in one frame. Implementations that track set `track_id`."""
