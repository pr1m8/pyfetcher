"""Page content model for :mod:`pyfetcher.db`."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from pyfetcher.db.models.base import Base, TimestampMixin, UUIDMixin


class Page(UUIDMixin, TimestampMixin, Base):
    """Fetched HTML page with extracted content and metadata.

    Stores the raw HTML alongside extracted text (trafilatura),
    markdown conversion, and structured metadata (Open Graph, JSON-LD).
    """

    __tablename__ = "pages"

    url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    hostname: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    html: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    og_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    structured_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    elapsed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
