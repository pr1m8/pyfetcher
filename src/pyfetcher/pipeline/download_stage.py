"""Download pipeline stage for :mod:`pyfetcher.pipeline`.

Purpose:
    Download media assets using yt-dlp, gallery-dl, or direct HTTP,
    then upload to MinIO and record in the database.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from pyfetcher.db.models.job import Job
from pyfetcher.db.models.media import MediaAsset
from pyfetcher.downloaders.direct import DirectDownloader
from pyfetcher.pipeline.stage import PipelineStage


class DownloadStage(PipelineStage):
    """Download stage: acquire binary assets and store in MinIO.

    Uses direct HTTP download by default. Can be extended to use
    yt-dlp or gallery-dl based on URL patterns or job payload hints.
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(job_type="download", **kwargs)  # type: ignore[arg-type]
        self._direct = DirectDownloader()

    async def process(self, job: Job, session: AsyncSession) -> dict | None:
        """Download a media asset and record it in the database."""
        page_id = None
        if job.payload and "page_id" in job.payload:
            page_id = uuid.UUID(job.payload["page_id"])

        results = await self._direct.download(job.url)
        if not results:
            return {"error": "no files downloaded"}

        result = results[0]

        # Upload to MinIO if store is available
        minio_key = None
        minio_bucket = None
        try:
            from pyfetcher.store.client import ObjectStoreClient
            from pyfetcher.store.keys import generate_media_key

            store = ObjectStoreClient()
            minio_key = generate_media_key(
                source_url=job.url,
                filename=result.filename,
                mime_type=result.mime_type,
            )
            minio_bucket = store._config.minio_bucket
            if result.local_path:
                await store.upload_file(minio_key, result.local_path)
        except ImportError:
            pass

        asset = MediaAsset(
            source_url=job.url,
            page_id=page_id,
            minio_bucket=minio_bucket or "local",
            minio_key=minio_key or (result.local_path or ""),
            filename=result.filename,
            file_size_bytes=result.file_size_bytes,
            checksum_sha256=result.checksum_sha256,
            extractor="direct",
        )
        session.add(asset)
        await session.flush()

        return {
            "asset_id": str(asset.id),
            "minio_key": minio_key,
            "file_size": result.file_size_bytes,
        }
