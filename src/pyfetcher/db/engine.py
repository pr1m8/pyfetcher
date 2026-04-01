"""Async database engine and session management for :mod:`pyfetcher`.

Purpose:
    Provide factory functions for creating async SQLAlchemy engines and
    session makers configured from :class:`~pyfetcher.config.PyfetcherConfig`.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pyfetcher.config import PyfetcherConfig


def build_async_engine(config: PyfetcherConfig | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine from config.

    Args:
        config: Application config. Uses defaults if not provided.

    Returns:
        A configured :class:`AsyncEngine`.
    """
    cfg = config or PyfetcherConfig()
    return create_async_engine(
        cfg.database_url,
        pool_size=cfg.db_pool_size,
        max_overflow=cfg.db_max_overflow,
        echo=False,
    )


def build_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine.

    Args:
        engine: The async engine to bind sessions to.

    Returns:
        An :class:`async_sessionmaker` producing :class:`AsyncSession` instances.
    """
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
