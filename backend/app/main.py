"""Composition root: builds the app and wires concrete implementations."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.core.errors import register_error_handlers
from app.core.logging import REQUEST_ID_HEADER, configure_logging, request_id_middleware
from app.features.health.routes import router as health_router
from app.features.sites.repository import SiteRepository
from app.features.sites.routes import router as sites_router
from app.features.sites.service import SiteService

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging()

    app = FastAPI(
        title="Data Nebula API",
        version="0.1.0",
        description="Read-only API over NISAR radar layers prepared offline by the pipeline.",
    )
    app.state.site_service = SiteService(SiteRepository(settings.data_dir))

    # Added last = outermost, so CORS headers are also set on error responses.
    app.middleware("http")(request_id_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    register_error_handlers(app)

    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(sites_router, prefix=API_PREFIX)
    return app


app = create_app()
