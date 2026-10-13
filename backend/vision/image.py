from __future__ import annotations

import numpy as np


def decode_image(data: bytes) -> np.ndarray:
    """Decode an encoded image (JPEG/PNG/WebP) into a BGR array. Raises ValueError."""
    import cv2

    if not data:
        raise ValueError("empty image")
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("unsupported or corrupted image")
    return image
