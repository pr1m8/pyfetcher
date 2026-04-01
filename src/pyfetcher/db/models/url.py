"""URL deduplication model for :mod:`pyfetcher.db`."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from pyfetcher.db.models.base import Base


class SeenURL(Base):
    """Tracks seen URLs for deduplication via xxhash64.

    The url_hash column is the primary key (BigInteger) holding the
    xxhash64 of the normalized URL for O(1) dedup lookups.
    """

    __tablename__ = "seen_urls"

    url_hash: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetch_count: Mapped[int] = mapped_column(Integer, default=0)
