"""FastAPI application factory.

Run with: uvicorn app.main:create_app --factory --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.container import Container, build_container
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.scheduler import build_scheduler

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or (container.settings if container else get_settings())
    configure_logging(settings.log_level, settings.log_json)
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        scheduler = build_scheduler(container) if settings.scheduler_enabled else None
        if scheduler:
            scheduler.start()
        logger.info(
            "%s %s started (env=%s, anomaly_engine=%s)",
            settings.app_name,
            __version__,
            settings.environment,
            container.anomaly_detector.name,
        )
        try:
            yield
        finally:
            if scheduler:
                scheduler.shutdown(wait=False)
            await container.database.dispose()
            logger.info("Shutdown complete")

    is_prod = settings.environment == "production"
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        description="Assistant IA de sécurité domestique : reconnaissance, anomalies, alertes.",
        lifespan=lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )
    app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app
