"""Ultralytics YOLO adapter (model 1), with optional ByteTrack multi-object tracking.

Licence note: Ultralytics is AGPL-3.0. Fine for the internship and demos; a commercial
product needs an Ultralytics enterprise licence or an alternative detector behind the same
`ObjectDetector` interface.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np

from vision.detection.base import ObjectDetector
from vision.types import BoundingBox, Detection


class YoloDetector(ObjectDetector):
    def __init__(
        self,
        weights: str | Path,
        *,
        confidence: float = 0.4,
        labels: Iterable[str] | None = None,
        track: bool = True,
        tracker_config: str = "bytetrack.yaml",
        image_size: int = 640,
        device: str | None = None,
    ) -> None:
        from ultralytics import YOLO

        self._model = YOLO(str(weights))
        self._confidence = confidence
        self._track = track
        self._tracker_config = tracker_config
        self._image_size = image_size
        self._device = device

        names: dict[int, str] = self._model.names
        wanted = set(labels) if labels else set(names.values())
        self._class_ids = [cid for cid, name in names.items() if name in wanted] or None
        self._names = names

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        kwargs = {
            "conf": self._confidence,
            "classes": self._class_ids,
            "imgsz": self._image_size,
            "device": self._device,
            "verbose": False,
        }
        if self._track:
            results = self._model.track(
                frame_bgr, persist=True, tracker=self._tracker_config, **kwargs
            )
        else:
            results = self._model.predict(frame_bgr, **kwargs)

        detections: list[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue
            ids = boxes.id.int().tolist() if boxes.id is not None else [None] * len(boxes)
            for xyxy, conf, cls, track_id in zip(
                boxes.xyxy.tolist(),
                boxes.conf.tolist(),
                boxes.cls.int().tolist(),
                ids,
                strict=True,
            ):
                detections.append(
                    Detection(
                        label=self._names[cls],
                        confidence=float(conf),
                        bbox=BoundingBox(*map(float, xyxy)),
                        track_id=track_id,
                    )
                )
        return detections
