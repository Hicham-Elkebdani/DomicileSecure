from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def l2_normalize(vector: np.ndarray | Sequence[float]) -> np.ndarray:
    array = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        raise ValueError("cannot normalise a zero vector")
    return array / norm


def vector_to_bytes(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def vector_from_bytes(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32).copy()


def cosine_similarities(matrix: np.ndarray, query: np.ndarray) -> np.ndarray:
    """Cosine similarity between each row of `matrix` and `query` (both L2-normalised)."""
    if matrix.size == 0:
        return np.empty(0, dtype=np.float32)
    return matrix @ query
