"""Async engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.base import Base


class Database:
    def __init__(self, url: str, *, echo: bool = False) -> None:
        kwargs: dict[str, Any] = {"echo": echo}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                kwargs["poolclass"] = StaticPool
        else:
            kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True)

        self.engine: AsyncEngine = create_async_engine(url, **kwargs)
        if url.startswith("sqlite"):
            self._configure_sqlite(self.engine)

        self.session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False, autoflush=False
        )

    @staticmethod
    def _configure_sqlite(engine: AsyncEngine) -> None:
        @event.listens_for(engine.sync_engine, "connect")
        def _set_pragmas(dbapi_connection: Any, _: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def ping(self) -> None:
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def create_all(self) -> None:
        """Create tables directly. Used by tests only; real databases use Alembic."""
        import app.models  # noqa: F401  (register models on the metadata)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()
