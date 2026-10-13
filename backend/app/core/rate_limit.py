"""In-memory sliding-window rate limiter.

Good enough for a single API instance (brute-force protection on login). When the API is
scaled horizontally, replace it with a shared store (e.g. Redis) behind the same interface.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self, max_hits: int, window_seconds: float = 60.0) -> None:
        self._max_hits = max_hits
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def hit(self, key: str) -> bool:
        """Record a hit for `key`. Returns False when the limit is exceeded."""
        now = time.monotonic()
        async with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self._window:
                bucket.popleft()
            if len(bucket) >= self._max_hits:
                return False
            bucket.append(now)
            return True

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._hits.pop(key, None)
