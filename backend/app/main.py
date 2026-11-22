"""
UtsavOps — FastAPI Application Entry Point
The self-healing AI operating system for India's festive commerce.
"""
# Compatibility patch for Starlette 1.10.x with FastAPI 0.111.x
import starlette.routing
starlette.routing.Router.on_startup = []
starlette.routing.Router.on_shutdown = []
_orig_router_init = starlette.routing.Router.__init__
def _compat_router_init(self, *args, on_startup=None, on_shutdown=None, **kwargs):
    self.on_startup = list(on_startup or [])
    self.on_shutdown = list(on_shutdown or [])
    _orig_router_init(self, *args, **kwargs)
starlette.routing.Router.__init__ = _compat_router_init

import fastapi
fastapi.FastAPI.max_body_size = None

import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db, close_db

import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()
    logger.info("Starting UtsavOps", env=settings.app_env)

    # Initialize database
    if settings.is_sqlite:
        await init_db()
        logger.info("SQLite database initialized")
    else:
        logger.info("Using PostgreSQL", url=settings.database_url[:30] + "...")

    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Log integration status
    logger.info(
        "Integration status",
        sarvam=settings.has_sarvam,
        flagsmith=settings.has_flagsmith,
        google_maps=settings.has_google_maps,
        nudgebee=settings.has_nudgebee,
        gemini=settings.has_gemini,
    )

    yield

    # Shutdown
    await close_db()
    logger.info("UtsavOps shut down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="UtsavOps API",
        description="The self-healing AI operating system for India's festive commerce",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import and register routers
    from app.routers import health, dashboard, orders, customers, dispatch, flags, aiops, audit
    app.include_router(health.router, prefix="/api", tags=["Health"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
    app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])
    app.include_router(dispatch.router, prefix="/api/dispatch", tags=["Dispatch"])
    app.include_router(flags.router, prefix="/api/flags", tags=["Feature Flags"])
    app.include_router(aiops.router, prefix="/api/aiops", tags=["AIOps"])
    app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc) if settings.app_debug else None},
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
