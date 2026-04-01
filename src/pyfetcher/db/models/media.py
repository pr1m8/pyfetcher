"""Media asset model for :mod:`pyfetcher.db`."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from pyfetcher.db.models.base import Base, TimestampMixin, UUIDMixin


class MediaAsset(UUIDMixin, TimestampMixin, Base):
    """Binary media asset stored in MinIO with metadata.

    References the source page and stores the MinIO object key along
    with extracted media metadata (EXIF, audio tags, video info, etc.).
    """

    __tablename__ = "media_assets"

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pages.id"), nullable=True
    )
    minio_bucket: Mapped[str] = mapped_column(Text, nullable=False)
    minio_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extractor: Mapped[str | None] = mapped_column(Text, nullable=True)
    extractor_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
