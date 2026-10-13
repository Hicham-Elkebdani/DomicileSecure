"""Export real events from the database to the training CSV format.

    python -m training.export_events --out data/real/events.csv --days 60

Combine with the synthetic dataset, or fine-tune on real data once enough has been collected
(a few weeks of normal routine is a good start). Alerts marked as "dismissed" (false
positives) are useful feedback to check the retrained model does not repeat them.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
from pathlib import Path

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.session import Database
from app.repositories.event import EventRepository
from training.dataset import write_events


async def export(out: Path, days: int) -> int:
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        async with database.session() as session:
            end = utcnow()
            events = await EventRepository(session).list_between(end - timedelta(days=days), end)
    finally:
        await database.dispose()
    return write_events(
        out,
        (
            {
                "occurred_at": e.occurred_at.isoformat(),
                "camera": str(e.camera_id),
                "kind": str(e.kind),
                "label": e.label,
                "identity": str(e.identity) if e.identity else "",
            }
            for e in events
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/real/events.csv"))
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()
    count = asyncio.run(export(args.out, args.days))
    print(f"{count} events exported to {args.out}")


if __name__ == "__main__":
    main()
