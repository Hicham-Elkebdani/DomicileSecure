"""Face detection (YuNet) + recognition (SFace), both shipped with OpenCV.

Why this stack rather than InsightFace or dlib:
* installs with a plain `pip install opencv-python` on Windows, Linux and macOS (no C++ build);
* both models come from the OpenCV Zoo under the Apache-2.0 licence (commercial use allowed);
* ~99.4 % accuracy on LFW for a 37 MB model that runs in real time on CPU.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from vision.face.base import FaceEmbedder
from vision.face.similarity import l2_normalize
from vision.types import BoundingBox, FaceEmbedding

_MAX_DETECTION_SIDE = 1280


class SFaceEmbedder(FaceEmbedder):
    def __init__(
        self,
        detector_model: Path,
        recognizer_model: Path,
        *,
        score_threshold: float = 0.8,
        nms_threshold: float = 0.3,
    ) -> None:
        for path in (detector_model, recognizer_model):
            if not Path(path).is_file():
                raise FileNotFoundError(
                    f"Model file not found: {path}. Run `python scripts/download_models.py`."
                )
        import cv2

        self._cv2 = cv2
        self._detector = cv2.FaceDetectorYN.create(
            str(detector_model), "", (320, 320), score_threshold, nms_threshold, 5000
        )
        self._recognizer = cv2.FaceRecognizerSF.create(str(recognizer_model), "")
        # OpenCV DNN objects are not thread-safe; the API calls us from a thread pool.
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return "sface-2021dec"

    @property
    def embedding_dim(self) -> int:
        return 128

    def embed(self, image_bgr: np.ndarray) -> list[FaceEmbedding]:
        if image_bgr is None or image_bgr.size == 0:
            return []
        height, width = image_bgr.shape[:2]
        scale = min(1.0, _MAX_DETECTION_SIDE / max(height, width))
        small = (
            self._cv2.resize(image_bgr, (int(width * scale), int(height * scale)))
            if scale < 1.0
            else image_bgr
        )

        results: list[FaceEmbedding] = []
        with self._lock:
            self._detector.setInputSize((small.shape[1], small.shape[0]))
            _, faces = self._detector.detect(small)
            if faces is None:
                return []
            for row in faces:
                face = row.copy()
                face[:14] /= scale  # bbox + 5 landmarks back to original resolution
                aligned = self._recognizer.alignCrop(image_bgr, face)
                feature = self._recognizer.feature(aligned)
                x, y, w, h = (float(v) for v in face[:4])
                results.append(
                    FaceEmbedding(
                        bbox=BoundingBox(x, y, x + w, y + h),
                        detection_score=float(face[14]),
                        vector=l2_normalize(feature),
                        model_name=self.model_name,
                    )
                )
        results.sort(key=lambda f: f.bbox.area, reverse=True)
        return results
