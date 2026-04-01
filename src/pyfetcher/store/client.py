"""Async object storage client for :mod:`pyfetcher.store`.

Purpose:
    Provide an async client for MinIO/S3 operations: upload, download,
    delete, list, and presigned URL generation. Uses aioboto3 for async
    S3 compatibility.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aioboto3

from pyfetcher.config import PyfetcherConfig


class ObjectStoreClient:
    """Async object storage client for MinIO/S3.

    Provides upload, download, delete, and presigned URL operations
    using aioboto3's async S3 interface against a MinIO endpoint.

    Args:
        config: Application configuration with MinIO connection details.
    """

    def __init__(self, config: PyfetcherConfig | None = None) -> None:
        self._config = config or PyfetcherConfig()
        self._session = aioboto3.Session()

    def _client_kwargs(self) -> dict[str, Any]:
        """Build kwargs for the S3 client context manager."""
        return {
            "service_name": "s3",
            "endpoint_url": f"{'https' if self._config.minio_secure else 'http'}://{self._config.minio_endpoint}",
            "aws_access_key_id": self._config.minio_access_key,
            "aws_secret_access_key": self._config.minio_secret_key,
        }

    async def ensure_bucket(self, bucket: str | None = None) -> None:
        """Create the bucket if it doesn't exist.

        Args:
            bucket: Bucket name. Defaults to config bucket.
        """
        bucket = bucket or self._config.minio_bucket
        async with self._session.client(**self._client_kwargs()) as s3:
            try:
                await s3.head_bucket(Bucket=bucket)
            except Exception:
                await s3.create_bucket(Bucket=bucket)

    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        *,
        bucket: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Upload bytes to object storage.

        Args:
            key: Object key.
            data: Bytes to upload.
            bucket: Bucket name. Defaults to config bucket.
            content_type: Optional MIME type.

        Returns:
            The object key.
        """
        bucket = bucket or self._config.minio_bucket
        extra: dict[str, str] = {}
        if content_type:
            extra["ContentType"] = content_type
        async with self._session.client(**self._client_kwargs()) as s3:
            await s3.put_object(Bucket=bucket, Key=key, Body=data, **extra)
        return key

    async def upload_file(
        self,
        key: str,
        file_path: str | Path,
        *,
        bucket: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Upload a local file to object storage.

        Args:
            key: Object key.
            file_path: Local file path.
            bucket: Bucket name. Defaults to config bucket.
            content_type: Optional MIME type.

        Returns:
            The object key.
        """
        bucket = bucket or self._config.minio_bucket
        extra_args: dict[str, str] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        async with self._session.client(**self._client_kwargs()) as s3:
            await s3.upload_file(str(file_path), bucket, key, ExtraArgs=extra_args or None)
        return key

    async def download_bytes(self, key: str, *, bucket: str | None = None) -> bytes:
        """Download an object as bytes.

        Args:
            key: Object key.
            bucket: Bucket name. Defaults to config bucket.

        Returns:
            The object contents as bytes.
        """
        bucket = bucket or self._config.minio_bucket
        async with self._session.client(**self._client_kwargs()) as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            return await response["Body"].read()

    async def presigned_get_url(
        self, key: str, *, bucket: str | None = None, expires_in: int = 3600
    ) -> str:
        """Generate a presigned GET URL.

        Args:
            key: Object key.
            bucket: Bucket name. Defaults to config bucket.
            expires_in: URL expiration in seconds.

        Returns:
            A presigned URL string.
        """
        bucket = bucket or self._config.minio_bucket
        async with self._session.client(**self._client_kwargs()) as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )

    async def delete(self, key: str, *, bucket: str | None = None) -> None:
        """Delete an object.

        Args:
            key: Object key.
            bucket: Bucket name. Defaults to config bucket.
        """
        bucket = bucket or self._config.minio_bucket
        async with self._session.client(**self._client_kwargs()) as s3:
            await s3.delete_object(Bucket=bucket, Key=key)

    async def list_keys(
        self, prefix: str = "", *, bucket: str | None = None, max_keys: int = 1000
    ) -> list[str]:
        """List object keys under a prefix.

        Args:
            prefix: Key prefix filter.
            bucket: Bucket name. Defaults to config bucket.
            max_keys: Maximum keys to return.

        Returns:
            A list of matching object keys.
        """
        bucket = bucket or self._config.minio_bucket
        async with self._session.client(**self._client_kwargs()) as s3:
            response = await s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys)
            return [obj["Key"] for obj in response.get("Contents", [])]
