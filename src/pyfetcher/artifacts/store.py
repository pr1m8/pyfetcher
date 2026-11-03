"""Blob-store protocol and dependency-free reference implementations.

Purpose:
    Give pipelines one storage contract for raw responses, structured item
    manifests, media, galleries, and exports without making S3 a core
    dependency.

Design:
    Queue and workflow messages carry :class:`~pyfetcher.artifacts.BlobRef`
    values, never large byte payloads. Concrete S3/MinIO integration remains an
    optional adapter.
"""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from pyfetcher.artifacts.models import BlobRef


class BlobStore(Protocol):
    """Async storage contract used by job templates and runtimes."""

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        media_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobRef: ...

    async def put_file(
        self,
        key: str,
        path: str | Path,
        *,
        media_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobRef: ...

    async def get_bytes(self, ref: BlobRef) -> bytes: ...

    async def exists(self, ref: BlobRef) -> bool: ...

    async def delete(self, ref: BlobRef) -> None: ...


def _safe_key(key: str) -> Path:
    path = Path(key)
    if not key or path.is_absolute() or ".." in path.parts:
        raise ValueError("blob key must be a non-empty relative path without parent traversal")
    return path


def _ref(
    *,
    provider: str,
    uri: str,
    key: str,
    data: bytes,
    media_type: str | None,
    metadata: Mapping[str, str] | None,
) -> BlobRef:
    return BlobRef(
        uri=uri,
        provider=provider,
        key=key,
        media_type=media_type,
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
        metadata=dict(metadata or {}),
    )


class MemoryBlobStore:
    """In-memory blob store for tests and ephemeral local runs."""

    def __init__(self, *, namespace: str = "default") -> None:
        self._namespace = namespace
        self._data: dict[str, bytes] = {}
        self._refs: dict[str, BlobRef] = {}

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        media_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobRef:
        normalized = _safe_key(key).as_posix()
        payload = bytes(data)
        ref = _ref(
            provider="memory",
            uri=f"memory://{quote(self._namespace)}/{quote(normalized)}",
            key=normalized,
            data=payload,
            media_type=media_type,
            metadata=metadata,
        )
        self._data[normalized] = payload
        self._refs[normalized] = ref
        return ref

    async def put_file(
        self,
        key: str,
        path: str | Path,
        *,
        media_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobRef:
        data = await asyncio.to_thread(Path(path).read_bytes)
        return await self.put_bytes(key, data, media_type=media_type, metadata=metadata)

    async def get_bytes(self, ref: BlobRef) -> bytes:
        try:
            return self._data[ref.key]
        except KeyError as exc:
            raise FileNotFoundError(ref.uri) from exc

    async def exists(self, ref: BlobRef) -> bool:
        return ref.key in self._data

    async def delete(self, ref: BlobRef) -> None:
        self._data.pop(ref.key, None)
        self._refs.pop(ref.key, None)


class LocalBlobStore:
    """Atomic filesystem-backed blob store rooted at one explicit directory."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        relative = _safe_key(key)
        path = (self._root / relative).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("blob key resolves outside the configured root")
        return path

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        media_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobRef:
        path = self._path(key)
        payload = bytes(data)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".part",
                delete=False,
            ) as temporary:
                partial = Path(temporary.name)
                temporary.write(payload)
            try:
                partial.replace(path)
            except BaseException:
                partial.unlink(missing_ok=True)
                raise

        await asyncio.to_thread(write)
        return _ref(
            provider="local",
            uri=path.as_uri(),
            key=_safe_key(key).as_posix(),
            data=payload,
            media_type=media_type,
            metadata=metadata,
        )

    async def put_file(
        self,
        key: str,
        path: str | Path,
        *,
        media_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobRef:
        destination = self._path(key)
        source = Path(path)

        def copy() -> tuple[int, str]:
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            size = 0
            with (
                source.open("rb") as reader,
                tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=destination.parent,
                    prefix=f".{destination.name}.",
                    suffix=".part",
                    delete=False,
                ) as temporary,
            ):
                partial = Path(temporary.name)
                while chunk := reader.read(1024 * 1024):
                    temporary.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            try:
                partial.replace(destination)
            except BaseException:
                partial.unlink(missing_ok=True)
                raise
            return size, digest.hexdigest()

        size, checksum = await asyncio.to_thread(copy)
        normalized = _safe_key(key).as_posix()
        return BlobRef(
            provider="local",
            uri=destination.as_uri(),
            key=normalized,
            media_type=media_type,
            size_bytes=size,
            checksum_sha256=checksum,
            metadata=dict(metadata or {}),
        )

    async def get_bytes(self, ref: BlobRef) -> bytes:
        return await asyncio.to_thread(self._path(ref.key).read_bytes)

    async def exists(self, ref: BlobRef) -> bool:
        return await asyncio.to_thread(self._path(ref.key).exists)

    async def delete(self, ref: BlobRef) -> None:
        await asyncio.to_thread(self._path(ref.key).unlink, missing_ok=True)


class S3BlobStore:
    """BlobStore adapter over an injected S3/MinIO ``ObjectStoreClient``."""

    def __init__(self, client: object, *, bucket: str) -> None:
        if not bucket.strip():
            raise ValueError("S3 blob bucket cannot be empty")
        self._client = client
        self._bucket = bucket

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        media_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobRef:
        normalized = _safe_key(key).as_posix()
        payload = bytes(data)
        await self._client.upload_bytes(  # type: ignore[union-attr]
            normalized,
            payload,
            bucket=self._bucket,
            content_type=media_type,
        )
        return _ref(
            provider="s3",
            uri=f"s3://{self._bucket}/{quote(normalized)}",
            key=normalized,
            data=payload,
            media_type=media_type,
            metadata=metadata,
        ).model_copy(update={"bucket": self._bucket})

    async def put_file(
        self,
        key: str,
        path: str | Path,
        *,
        media_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> BlobRef:
        normalized = _safe_key(key).as_posix()
        source = Path(path)
        await self._client.upload_file(  # type: ignore[union-attr]
            normalized,
            source,
            bucket=self._bucket,
            content_type=media_type,
        )

        def checksum() -> tuple[int, str]:
            digest = hashlib.sha256()
            size = 0
            with source.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
            return size, digest.hexdigest()

        size, digest = await asyncio.to_thread(checksum)
        return BlobRef(
            provider="s3",
            uri=f"s3://{self._bucket}/{quote(normalized)}",
            key=normalized,
            bucket=self._bucket,
            media_type=media_type,
            size_bytes=size,
            checksum_sha256=digest,
            metadata=dict(metadata or {}),
        )

    async def get_bytes(self, ref: BlobRef) -> bytes:
        return await self._client.download_bytes(  # type: ignore[union-attr]
            ref.key,
            bucket=ref.bucket or self._bucket,
        )

    async def exists(self, ref: BlobRef) -> bool:
        return await self._client.exists(  # type: ignore[union-attr]
            ref.key,
            bucket=ref.bucket or self._bucket,
        )

    async def delete(self, ref: BlobRef) -> None:
        await self._client.delete(  # type: ignore[union-attr]
            ref.key,
            bucket=ref.bucket or self._bucket,
        )


__all__ = ["BlobStore", "LocalBlobStore", "MemoryBlobStore", "S3BlobStore"]
