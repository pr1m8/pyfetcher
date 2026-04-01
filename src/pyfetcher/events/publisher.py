"""Event publisher using Postgres NOTIFY for :mod:`pyfetcher.events`."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class EventPublisher:
    """Publishes events via Postgres NOTIFY.

    Payloads are typically job UUIDs (well within the 8000 byte limit).

    Args:
        session: Async database session for executing NOTIFY.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(self, channel: str, payload: str) -> None:
        """Send a NOTIFY on the given channel.

        Args:
            channel: The channel name (e.g. ``Channels.CRAWL_JOBS``).
            payload: The notification payload (typically a job UUID string).
        """
        await self._session.execute(text(f"NOTIFY {channel}, :payload"), {"payload": payload})
