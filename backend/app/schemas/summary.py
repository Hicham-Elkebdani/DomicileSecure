from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class DailySummaryRead(BaseModel):
    day: date
    text: str
    stats: dict[str, Any]
    generated_at: datetime | None = None
    is_final: bool = False
