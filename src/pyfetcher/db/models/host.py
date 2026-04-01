"""Per-host rules and scheduling model for :mod:`pyfetcher.db`."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from pyfetcher.db.models.base import Base, TimestampMixin, UUIDMixin


class Host(UUIDMixin, TimestampMixin, Base):
    """Per-host crawl rules, robots.txt cache, and scheduling state.

    Tracks the politeness constraints and next-safe-fetch time for each
    hostname to enforce responsible crawling.
    """

    __tablename__ = "hosts"

    hostname: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    robots_txt: Mapped[str | None] = mapped_column(Text, nullable=True)
    robots_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    crawl_delay_seconds: Mapped[float] = mapped_column(Float, default=1.0)
    min_request_interval_ms: Mapped[int] = mapped_column(Integer, default=1000)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_safe_fetch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
