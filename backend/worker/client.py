"""HTTP client for the ingest API, resilient to short API outages.

Observations are buffered locally and retried, so a restart of the API does not lose events.
The buffer is bounded: during a long outage the oldest observations are dropped first.
"""

from __future__ import annotations

import logging
import uuid
from collections import deque

import httpx

from app.schemas.ingest import Observation, ObservationBatch

logger = logging.getLogger(__name__)

_BATCH_SIZE = 200


class WorkerAuthenticationError(RuntimeError):
    """The API rejected the worker key: retrying is pointless."""


class IngestClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        camera_id: uuid.UUID,
        *,
        max_buffer: int = 2000,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._camera_id = camera_id
        self._buffer: deque[Observation] = deque(maxlen=max_buffer)
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=timeout,
            transport=transport,
        )

    @property
    def pending(self) -> int:
        return len(self._buffer)

    def enqueue(self, observations: list[Observation]) -> None:
        if len(self._buffer) + len(observations) > (self._buffer.maxlen or 0):
            logger.warning("Observation buffer full, oldest observations will be dropped")
        self._buffer.extend(observations)

    def flush(self) -> int:
        """Send buffered observations. Returns how many were delivered."""
        delivered = 0
        while self._buffer:
            batch = [self._buffer[i] for i in range(min(_BATCH_SIZE, len(self._buffer)))]
            payload = ObservationBatch(camera_id=self._camera_id, observations=batch)
            try:
                response = self._http.post(
                    "/ingest/observations",
                    content=payload.model_dump_json(),
                    headers={"Content-Type": "application/json"},
                )
            except httpx.HTTPError as exc:
                logger.warning("API unreachable (%s), %d observations kept", exc, self.pending)
                return delivered

            if response.status_code == 401:
                raise WorkerAuthenticationError("Invalid WORKER_API_KEY")
            if response.status_code >= 500:
                logger.warning("API error %s, will retry", response.status_code)
                return delivered
            for _ in batch:
                self._buffer.popleft()
            if response.status_code >= 400:
                # Retrying a rejected payload would block the queue forever.
                logger.error("Batch rejected (%s): %s", response.status_code, response.text[:500])
                continue
            delivered += len(batch)
            result = response.json()
            if result.get("alerts_created"):
                logger.info("API raised %s alert(s)", result["alerts_created"])
        return delivered

    def heartbeat(self) -> None:
        try:
            response = self._http.post(f"/ingest/cameras/{self._camera_id}/heartbeat")
            if response.status_code == 401:
                raise WorkerAuthenticationError("Invalid WORKER_API_KEY")
            if response.status_code == 404:
                logger.error("Camera %s is not registered in the API", self._camera_id)
        except httpx.HTTPError as exc:
            logger.warning("Heartbeat failed: %s", exc)

    def close(self) -> None:
        self._http.close()
