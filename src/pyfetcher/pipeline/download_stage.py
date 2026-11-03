"""Download pipeline stage for :mod:`pyfetcher.pipeline`.

Purpose:
    Download media assets using yt-dlp, gallery-dl, or direct HTTP,
    then upload to MinIO and record in the database.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from pyfetcher.acquisition.models import AcquisitionRequest
from pyfetcher.acquisition.service import AcquisitionService
from pyfetcher.db.models.job import Job
from pyfetcher.db.models.media import MediaAsset
from pyfetcher.pipeline.stage import PipelineStage


class DownloadStage(PipelineStage):
    """Download stage: acquire binary assets and store in MinIO.

    Uses the provider-neutral acquisition service, so jobs can select direct
    HTTP, yt-dlp, gallery-dl, or a registered custom provider. One database
    row is created for every downloaded item, including gallery and playlist
    results.
    """

    def __init__(
        self,
        *,
        acquisition_service: AcquisitionService | None = None,
        object_store: Any | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(job_type="download", **kwargs)  # type: ignore[arg-type]
        self._owns_acquisition_service = acquisition_service is None
        self._acquisition = acquisition_service or AcquisitionService()
        self._store = object_store
        self._store_resolved = object_store is not None

    async def process(self, job: Job, session: AsyncSession) -> dict | None:
        """Acquire media assets and record every downloaded item."""
        payload = job.payload or {}
        page_id = None
        if "page_id" in payload:
            page_id = uuid.UUID(payload["page_id"])

        request_fields = {
            name: payload[name]
            for name in (
                "provider",
                "output_dir",
                "headers",
                "cookies",
                "proxy",
                "credential_ref",
                "filename_template",
                "overwrite",
                "timeout_seconds",
                "retries",
                "direct_options",
                "yt_dlp_options",
                "gallery_dl_options",
                "provider_options",
            )
            if name in payload
        }
        result = await self._acquisition.acquire(
            AcquisitionRequest(url=job.url, operation="download", **request_fields)
        )
        if not result.downloads:
            return {"error": "no files downloaded"}

        store = self._resolve_store()
        asset_ids: list[str] = []
        stored_items: list[dict[str, Any]] = []
        for download in result.downloads:
            object_key = download.minio_key
            object_bucket = download.minio_bucket
            if store is not None and download.local_path:
                from pyfetcher.store.keys import generate_media_key

                object_key = object_key or generate_media_key(
                    source_url=download.source_url or job.url,
                    filename=download.filename,
                    mime_type=download.mime_type,
                )
                object_bucket = object_bucket or store.default_bucket
                await store.upload_file(
                    object_key,
                    download.local_path,
                    bucket=object_bucket,
                    content_type=download.mime_type,
                )

            metadata = download.to_metadata()
            extractor = (
                download.media_info.extractor
                if download.media_info is not None
                else result.provenance.extractor
            )
            asset = MediaAsset(
                source_url=download.source_url or job.url,
                page_id=page_id,
                minio_bucket=object_bucket or "local",
                minio_key=object_key or (download.local_path or ""),
                filename=download.filename,
                mime_type=download.mime_type,
                file_size_bytes=download.file_size_bytes,
                checksum_sha256=download.checksum_sha256,
                media_metadata=metadata.model_dump(mode="json"),
                extractor=extractor or result.provider,
                extractor_metadata=(
                    download.media_info.extra if download.media_info is not None else None
                ),
            )
            session.add(asset)
            await session.flush()
            asset_id = str(asset.id)
            asset_ids.append(asset_id)
            stored_items.append(
                {
                    "asset_id": asset_id,
                    "source_url": asset.source_url,
                    "object_key": object_key,
                    "file_size": download.file_size_bytes,
                }
            )

        first = stored_items[0]
        return {
            "provider": result.provider,
            "asset_id": first["asset_id"],
            "asset_ids": asset_ids,
            "minio_key": first["object_key"],
            "file_size": first["file_size"],
            "items": stored_items,
        }

    def _resolve_store(self) -> Any | None:
        """Resolve the optional object store once without making it core."""
        if self._store_resolved:
            return self._store
        self._store_resolved = True
        try:
            from pyfetcher.store.client import ObjectStoreClient
        except ImportError:
            self._store = None
        else:
            self._store = ObjectStoreClient()
        return self._store

    async def aclose(self) -> None:
        """Close providers when this stage created the acquisition service."""
        if self._owns_acquisition_service:
            await self._acquisition.aclose()
