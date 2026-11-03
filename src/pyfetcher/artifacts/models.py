"""Serializable references for pipeline artifacts and collections.

Purpose:
    Keep large bodies and files out of jobs, queues, workflow histories, and
    API payloads while preserving their identity, provenance, and shape.

Design:
    A :class:`BlobRef` addresses bytes in a storage backend. An
    :class:`ArtifactRef` describes what those bytes mean. Collections model
    galleries, playlists, paginated result sets, and related groups without
    coupling them to a downloader or queue implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class BlobRef(BaseModel):
    """Immutable address and integrity metadata for stored bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    uri: str
    provider: str
    key: str
    bucket: str | None = None
    media_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    checksum_sha256: str | None = None
    etag: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("uri")
    @classmethod
    def _validate_uri(cls, value: str) -> str:
        if "://" not in value:
            raise ValueError("blob URI must include a scheme")
        return value


class ArtifactRef(BaseModel):
    """Typed pipeline artifact with optional stored bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    kind: str
    source_url: str | None = None
    blob: BlobRef | None = None
    media_type: str | None = None
    name: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("kind")
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "_")
        if not normalized:
            raise ValueError("artifact kind cannot be empty")
        return normalized


class ArtifactMember(BaseModel):
    """One ordered relationship from a collection to an artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact: ArtifactRef
    position: int = Field(ge=0)
    relationship: str = "member"
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ArtifactCollection(BaseModel):
    """Ordered gallery, playlist, page set, search result, or other group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    kind: str
    source_url: str | None = None
    title: str | None = None
    members: tuple[ArtifactMember, ...] = ()
    continuation_token: str | None = None
    manifest: BlobRef | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("kind")
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "_")
        if not normalized:
            raise ValueError("collection kind cannot be empty")
        return normalized


__all__ = ["ArtifactCollection", "ArtifactMember", "ArtifactRef", "BlobRef"]
