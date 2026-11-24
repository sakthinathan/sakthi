"""
Database engine, session management, and resilience layer.
Supports Cloud SQL PostgreSQL (production) with automatic graceful fallback to SQLite
when external network or Cloud SQL access is unavailable.
"""
import uuid
import structlog
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, text
from typing import AsyncGenerator, Optional

from app.config import get_settings

logger = structlog.get_logger()


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def generate_uuid() -> str:
    """Generate a UUID string for use as primary key."""
    return str(uuid.uuid4())


def _build_engine(database_url: str, is_sqlite: bool):
    """Create async SQLAlchemy engine with connection pooling and timeouts"""
    settings = get_settings()

    if is_sqlite:
        connect_args = {"check_same_thread": False}
        return create_async_engine(
            database_url,
            echo=False,
            connect_args=connect_args,
        )

    # Cloud SQL PostgreSQL via asyncpg
    connect_args = {
        "command_timeout": settings.db_command_timeout,
        "timeout": 10,
    }
    return create_async_engine(
        database_url,
        echo=False,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


settings = get_settings()
_active_db_url = settings.database_url
_is_sqlite_mode = settings.is_sqlite

engine = _build_engine(_active_db_url, _is_sqlite_mode)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_health(session: Optional[AsyncSession] = None) -> dict:
    """
    Test live database connection without throwing unhandled exceptions.
    Returns status dict without exposing credentials.
    """
    global engine, AsyncSessionLocal, _active_db_url, _is_sqlite_mode
    try:
        if session is not None:
            await session.execute(text("SELECT 1"))
            return {
                "status": "connected",
                "type": "sqlite" if _is_sqlite_mode else "cloud_sql_postgresql",
                "host": "local" if _is_sqlite_mode else settings.db_host,
                "database": "utsavops",
                "error": None,
            }
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "type": "sqlite" if _is_sqlite_mode else "cloud_sql_postgresql",
            "host": "local" if _is_sqlite_mode else settings.db_host,
            "database": "utsavops",
            "error": None,
        }
    except Exception as e:
        error_msg = str(e)
        # Redact any accidental credential leaks from error message
        if settings.db_password and settings.db_password in error_msg:
            error_msg = error_msg.replace(settings.db_password, "******")
        logger.warn("Database connection probe failed", error=error_msg)
        return {
            "status": "disconnected",
            "type": "sqlite" if _is_sqlite_mode else "cloud_sql_postgresql",
            "host": "local" if _is_sqlite_mode else settings.db_host,
            "database": "utsavops",
            "error": error_msg,
        }


async def init_db():
    """
    Initialize database schema.
    Attempts Cloud SQL first. If unreachable (e.g. network restrictions or private IP),
    switches gracefully to local SQLite so the system remains available.
    """
    global engine, AsyncSessionLocal, _active_db_url, _is_sqlite_mode
    settings = get_settings()

    if not _is_sqlite_mode:
        logger.info(
            "Connecting to Cloud SQL PostgreSQL",
            host=settings.db_host,
            database=settings.db_name,
            region=settings.gcp_region,
        )
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Successfully connected to Cloud SQL PostgreSQL and verified schema")
            return
        except Exception as e:
            logger.error(
                "Cloud SQL PostgreSQL connection failed in live mode. "
                "Silent SQLite fallback is disabled to prevent data desynchronization.",
                host=settings.db_host,
                error=type(e).__name__,
            )
            raise RuntimeError(
                f"Configured live database connection to Cloud SQL PostgreSQL failed: {type(e).__name__}. "
                "A configured live database must not silently fall back to SQLite."
            ) from e

    # SQLite table initialization
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized with resilient SQLite engine")


async def close_db():
    """Dispose of the database engine."""
    await engine.dispose()
