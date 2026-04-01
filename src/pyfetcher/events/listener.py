"""Event listener using Postgres LISTEN for :mod:`pyfetcher.events`."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import asyncpg

from pyfetcher.config import PyfetcherConfig

logger = logging.getLogger("pyfetcher.events")


class EventListener:
    """Listens for Postgres NOTIFY events on specified channels.

    Uses a raw asyncpg connection (not SQLAlchemy) for LISTEN since
    SQLAlchemy's async session doesn't expose notification listeners.

    Args:
        config: Application configuration with database URL.
    """

    def __init__(self, config: PyfetcherConfig | None = None) -> None:
        self._config = config or PyfetcherConfig()
        self._connection: asyncpg.Connection | None = None
        self._handlers: dict[str, list[Callable[[str], Coroutine[Any, Any, None]]]] = {}
        self._running = False

    def on(self, channel: str, handler: Callable[[str], Coroutine[Any, Any, None]]) -> None:
        """Register a handler for a channel.

        Args:
            channel: The channel to listen on.
            handler: Async callable receiving the notification payload.
        """
        self._handlers.setdefault(channel, []).append(handler)

    async def _get_connection(self) -> asyncpg.Connection:
        """Get or create the asyncpg connection for LISTEN."""
        if self._connection is None or self._connection.is_closed():
            dsn = self._config.database_url.replace("+asyncpg", "").replace(
                "postgresql+asyncpg", "postgresql"
            )
            self._connection = await asyncpg.connect(dsn)
        return self._connection

    async def start(self) -> None:
        """Start listening on all registered channels.

        Runs indefinitely, dispatching notifications to registered
        handlers. Call :meth:`stop` to shut down.
        """
        conn = await self._get_connection()

        for channel in self._handlers:
            await conn.add_listener(channel, self._dispatch)
            logger.info("Listening on channel: %s", channel)

        self._running = True
        while self._running:
            await asyncio.sleep(1)

    def _dispatch(
        self,
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        """Dispatch a notification to registered handlers."""
        handlers = self._handlers.get(channel, [])
        for handler in handlers:
            asyncio.create_task(handler(payload))

    async def stop(self) -> None:
        """Stop listening and close the connection."""
        self._running = False
        if self._connection and not self._connection.is_closed():
            for channel in self._handlers:
                await self._connection.remove_listener(channel, self._dispatch)
            await self._connection.close()
            self._connection = None
