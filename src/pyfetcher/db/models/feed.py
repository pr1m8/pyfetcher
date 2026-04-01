"""RSS/Atom feed tracking model for :mod:`pyfetcher.db`."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from pyfetcher.db.models.base import Base, TimestampMixin, UUIDMixin


class Feed(UUIDMixin, TimestampMixin, Base):
    """RSS/Atom feed with polling state and adaptive interval.

    Tracks when a feed was last polled, the most recent entry hash
    for change detection, and an adaptive polling interval that adjusts
    based on publication frequency.
    """

    __tablename__ = "feeds"

    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_entry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_entry_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
