from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class FrameSource(ABC):
    @property
    @abstractmethod
    def is_live(self) -> bool:
        """Live streams reconnect forever; files end."""

    @abstractmethod
    def read(self) -> np.ndarray | None: ...

    @abstractmethod
    def release(self) -> None: ...


class OpenCVFrameSource(FrameSource):
    """Webcam, RTSP/HTTP stream or video file, with automatic reconnection for streams."""

    def __init__(self, source: str, *, max_backoff_seconds: float = 30.0) -> None:
        import cv2

        self._cv2 = cv2
        self._source: int | str = int(source) if source.isdigit() else source
        self._is_file = isinstance(self._source, str) and Path(self._source).is_file()
        self._max_backoff = max_backoff_seconds
        self._capture = self._open()

    @property
    def is_live(self) -> bool:
        return not self._is_file

    def _open(self):  # type: ignore[no-untyped-def]
        capture = self._cv2.VideoCapture(self._source)
        if not capture.isOpened():
            logger.warning("Cannot open video source %s", self._describe())
        return capture

    def _describe(self) -> str:
        # Never log RTSP credentials.
        text = str(self._source)
        return text.split("@")[-1] if "@" in text else text

    def read(self) -> np.ndarray | None:
        ok, frame = self._capture.read()
        if ok:
            return frame
        if self._is_file:
            return None
        self._reconnect()
        return None

    def _reconnect(self) -> None:
        delay = 1.0
        self._capture.release()
        while True:
            logger.warning("Stream lost, reconnecting to %s in %.0fs", self._describe(), delay)
            time.sleep(delay)
            self._capture = self._open()
            if self._capture.isOpened():
                logger.info("Reconnected to %s", self._describe())
                return
            delay = min(delay * 2, self._max_backoff)

    def release(self) -> None:
        self._capture.release()
