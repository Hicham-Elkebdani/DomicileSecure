from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app import models  # noqa: F401  (register tables)
from app.core.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
database_url = config.get_main_option("sqlalchemy.url") or get_settings().database_url


def _configure(connection: Connection | None = None) -> None:
    context.configure(
        connection=connection,
        url=None if connection else database_url,
        target_metadata=target_metadata,
        literal_binds=connection is None,
        compare_type=True,
        # SQLite cannot ALTER most things; batch mode recreates tables transparently.
        render_as_batch=database_url.startswith("sqlite"),
    )


def run_migrations_offline() -> None:
    _configure()
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
