"""Async SQLAlchemy database setup for PostgreSQL.

This module provides the core database infrastructure including:
- Async engine creation with PostgreSQL/asyncpg
- Session factory for dependency injection
- Base class for ORM models
- Database initialization utilities
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings


settings = get_settings()

# Create async engine with PostgreSQL + asyncpg driver
engine = create_async_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL query logging during development
    pool_pre_ping=True,  # Enable connection health checks
    pool_size=5,
    max_overflow=10,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    All model classes should inherit from this base to ensure
    proper table creation and relationship management.
    """

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for FastAPI dependency injection.

    This is an async generator that yields a database session and ensures
    proper cleanup after the request is complete.

    Yields:
        AsyncSession: An async SQLAlchemy session for database operations.

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database by creating all tables.

    This function should be called during application startup to ensure
    all ORM models have their corresponding tables created in the database.

    Note:
        This uses `create_all` which only creates tables that don't exist.
        It will not modify existing tables. For schema migrations, use Alembic.

    Example:
        @app.on_event("startup")
        async def startup():
            await init_db()
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close the database engine and release all connections.

    This function should be called during application shutdown to ensure
    proper cleanup of database resources.

    Example:
        @app.on_event("shutdown")
        async def shutdown():
            await close_db()
    """
    await engine.dispose()
