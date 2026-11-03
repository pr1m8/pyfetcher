"""Built-in reusable job templates for pagination, search, and media.

These templates deliberately depend on runtime services by stable names.
Serialized jobs contain only data and versioned template references; clients,
credentials, storage handles, and provider implementations stay in JobContext.
"""

from __future__ import annotations

import mimetypes
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from pyfetcher.acquisition import AcquisitionRequest
from pyfetcher.artifacts import ArtifactCollection, ArtifactMember, ArtifactRef, BlobRef
from pyfetcher.contracts import FetchRequest, FetchResponse
from pyfetcher.jobs.models import JobRequest, JobResult, TemplateRef
from pyfetcher.jobs.registry import JobContext, TemplateRegistry
from pyfetcher.search import SearchRequest

type PaginationMode = Literal["discover_last", "enumerate", "follow_next"]
type CollectionKind = Literal["gallery", "playlist", "collection", "media_set"]


class PaginationInput(BaseModel):
    """Portable pagination discovery and fan-out policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: PaginationMode = "discover_last"
    page_link_selector: str = "a[href]"
    next_link_selector: str | None = None
    page_parameter: str = "page"
    page_url_template: str | None = None
    first_page: int = Field(default=1, ge=0)
    max_pages: int = Field(default=1_000, ge=1, le=100_000)
    current_page: int = Field(default=1, ge=1)
    visit_template: TemplateRef | None = None
    visit_payload: dict[str, JsonValue] = Field(default_factory=dict)
    store_page: bool = False
    storage_prefix: str = "pages"


class MediaAcquisitionInput(BaseModel):
    """Provider-neutral media, gallery, or playlist acquisition policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["metadata", "download"] = "download"
    provider: str = "auto"
    output_dir: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    proxy: str | None = None
    credential_ref: str | None = None
    filename_template: str | None = None
    overwrite: bool = False
    timeout_seconds: float | None = Field(default=None, gt=0)
    retries: int = Field(default=3, ge=0)
    direct_options: dict[str, JsonValue] = Field(default_factory=dict)
    yt_dlp_options: dict[str, JsonValue] = Field(default_factory=dict)
    gallery_dl_options: dict[str, JsonValue] = Field(default_factory=dict)
    provider_options: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    collection_kind: CollectionKind = "media_set"
    collection_title: str | None = None
    store_downloads: bool = True
    storage_prefix: str = "media"


class SearchInput(BaseModel):
    """Job payload for a registered site-search adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    provider: str = "auto"
    limit: int = Field(default=20, ge=1, le=1_000)
    cursor: str | None = None
    filters: dict[str, JsonValue] = Field(default_factory=dict)
    visit_template: TemplateRef | None = None
    visit_payload: dict[str, JsonValue] = Field(default_factory=dict)


async def _fetch(context: JobContext, request: FetchRequest) -> FetchResponse:
    service = context.require("fetch")
    if hasattr(service, "send"):
        return cast(FetchResponse, await service.send(request))  # type: ignore[union-attr]
    if hasattr(service, "afetch"):
        return cast(FetchResponse, await service.afetch(request))  # type: ignore[union-attr]
    raise TypeError("runtime service 'fetch' must provide async send() or afetch()")


def _page_number(url: str, text: str, parameter: str) -> int | None:
    values = parse_qs(urlsplit(url).query).get(parameter, ())
    candidate = values[-1] if values else text.strip()
    match = re.search(r"\d+", candidate)
    return int(match.group()) if match else None


def _replace_query(url: str, name: str, value: int) -> str:
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    query[name] = [str(value)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), ""))


def _child(
    parent: JobRequest, ref: TemplateRef, url: str, payload: dict[str, JsonValue]
) -> JobRequest:
    return JobRequest(
        template=ref,
        target=url,
        payload=payload,
        policy=parent.policy,
        run_id=parent.run_id,
        parent_job_id=parent.id,
        idempotency_key=f"{ref.key}:{url}",
        trace=parent.trace,
    )


class PaginationTemplate:
    """Discover a last page, enumerate page URLs, or walk a next-link chain."""

    name = "web.pagination"
    version = "1"
    input_model = PaginationInput

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        started = datetime.now(UTC)
        if job.target is None:
            raise ValueError("pagination jobs require target URL")
        spec = PaginationInput.model_validate(job.payload)
        response = await _fetch(context, FetchRequest(url=job.target))
        html = response.text
        if html is None and response.body is not None:
            html = response.body.decode("utf-8", errors="replace")
        if html is None:
            raise ValueError("pagination response has no buffered HTML body")

        soup = BeautifulSoup(html, "html.parser")
        discovered: dict[int, str] = {}
        for node in soup.select(spec.page_link_selector):
            href = node.get("href")
            if not isinstance(href, str):
                continue
            absolute = urljoin(response.final_url, href)
            number = _page_number(absolute, node.get_text(" ", strip=True), spec.page_parameter)
            if number is not None:
                discovered[number] = absolute

        last_page = max(discovered, default=spec.current_page)
        page_urls: list[str] = []
        spawned: list[JobRequest] = []
        if spec.mode == "enumerate":
            last_page = min(last_page, spec.max_pages)
            for number in range(spec.first_page, last_page + 1):
                if spec.page_url_template is not None:
                    url = spec.page_url_template.format(page=number)
                else:
                    url = discovered.get(
                        number,
                        _replace_query(response.final_url, spec.page_parameter, number),
                    )
                page_urls.append(url)
                if spec.visit_template is not None:
                    spawned.append(_child(job, spec.visit_template, url, spec.visit_payload))
        elif spec.mode == "follow_next":
            page_urls.append(response.final_url)
            if spec.visit_template is not None:
                spawned.append(
                    _child(job, spec.visit_template, response.final_url, spec.visit_payload)
                )
            selector = spec.next_link_selector or 'a[rel="next"]'
            next_node = soup.select_one(selector)
            next_href = next_node.get("href") if next_node is not None else None
            if isinstance(next_href, str) and spec.current_page < spec.max_pages:
                next_url = urljoin(response.final_url, next_href)
                next_payload = spec.model_copy(
                    update={"current_page": spec.current_page + 1}
                ).model_dump(mode="json")
                spawned.append(
                    _child(
                        job,
                        TemplateRef(name=self.name, version=self.version),
                        next_url,
                        next_payload,
                    )
                )

        artifacts: list[ArtifactRef] = []
        if spec.store_page:
            if context.blob_store is None:
                raise RuntimeError("store_page requires a JobContext blob_store")
            key = f"{spec.storage_prefix.rstrip('/')}/{job.id}.html"
            blob = await context.blob_store.put_bytes(
                key,
                response.body if response.body is not None else html.encode(),
                media_type=response.content_type or "text/html",
                metadata={"source_url": response.final_url},
            )
            artifacts.append(
                ArtifactRef(
                    kind="web_page",
                    source_url=response.final_url,
                    blob=blob,
                    media_type=response.content_type or "text/html",
                )
            )

        return JobResult.succeeded(
            job,
            output={
                "mode": spec.mode,
                "last_page": last_page,
                "page_urls": page_urls,
                "next_page_scheduled": spec.mode == "follow_next"
                and len(spawned) > bool(spec.visit_template),
            },
            artifacts=tuple(artifacts),
            spawned_jobs=tuple(spawned),
            metrics={"pages_discovered": len(discovered), "jobs_spawned": len(spawned)},
            started_at=started,
        )


def _as_json(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): _as_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_as_json(item) for item in value]
    return str(value)


def _json_metadata(values: dict[str, object]) -> dict[str, JsonValue]:
    return {str(key): _as_json(value) for key, value in values.items()}


class MediaAcquisitionTemplate:
    """Run direct, yt-dlp, or gallery-dl acquisition and normalize artifacts."""

    name = "media.acquire"
    version = "1"
    input_model = MediaAcquisitionInput

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        started = datetime.now(UTC)
        if job.target is None:
            raise ValueError("media acquisition jobs require target URL")
        spec = MediaAcquisitionInput.model_validate(job.payload)
        service = context.require("acquisition")
        acquire = getattr(service, "acquire", None)
        if not callable(acquire):
            raise TypeError("runtime service 'acquisition' must provide async acquire()")
        request = AcquisitionRequest(
            url=job.target,
            operation=spec.operation,
            provider=spec.provider,
            output_dir=Path(spec.output_dir) if spec.output_dir else None,
            headers=spec.headers,
            proxy=spec.proxy,
            credential_ref=spec.credential_ref,
            filename_template=spec.filename_template,
            overwrite=spec.overwrite,
            timeout_seconds=spec.timeout_seconds,
            retries=spec.retries,
            direct_options=spec.direct_options,
            yt_dlp_options=spec.yt_dlp_options,
            gallery_dl_options=spec.gallery_dl_options,
            provider_options=spec.provider_options,
        )
        result = await acquire(request)
        artifacts: list[ArtifactRef] = []

        for position, media in enumerate(result.media):
            artifacts.append(
                ArtifactRef(
                    kind="media",
                    source_url=media.url,
                    media_type=media.mime_type,
                    name=media.title,
                    metadata={
                        "position": position,
                        "description": media.description,
                        "duration_seconds": media.duration_seconds,
                        "thumbnail_url": media.thumbnail_url,
                        "uploader": media.uploader,
                        "upload_date": media.upload_date,
                        "extension": media.ext,
                        **_json_metadata(media.extra),
                    },
                )
            )

        for position, download in enumerate(result.downloads):
            blob: BlobRef | None = None
            if download.local_path and spec.store_downloads:
                if context.blob_store is None:
                    raise RuntimeError("store_downloads requires a JobContext blob_store")
                filename = download.filename or Path(download.local_path).name
                key = f"{spec.storage_prefix.rstrip('/')}/{job.id}/{position:06d}-{filename}"
                blob = await context.blob_store.put_file(
                    key,
                    download.local_path,
                    media_type=download.mime_type or mimetypes.guess_type(filename)[0],
                    metadata={"source_url": download.source_url},
                )
            elif download.minio_key:
                bucket = download.minio_bucket or "default"
                blob = BlobRef(
                    uri=f"s3://{bucket}/{download.minio_key}",
                    provider="s3",
                    bucket=bucket,
                    key=download.minio_key,
                    media_type=download.mime_type,
                    size_bytes=download.file_size_bytes,
                    checksum_sha256=download.checksum_sha256,
                )
            artifacts.append(
                ArtifactRef(
                    kind="download",
                    source_url=download.source_url,
                    blob=blob,
                    media_type=download.mime_type,
                    name=download.filename,
                    metadata={"position": position, **_json_metadata(download.media_metadata)},
                )
            )

        collection = ArtifactCollection(
            kind=spec.collection_kind,
            source_url=result.source_url,
            title=spec.collection_title,
            members=tuple(
                ArtifactMember(artifact=artifact, position=position)
                for position, artifact in enumerate(artifacts)
            ),
            metadata={
                "provider": result.provider,
                "operation": result.operation,
                "extractor": result.provenance.extractor,
            },
        )
        return JobResult.succeeded(
            job,
            output={"provider": result.provider, "item_count": result.item_count},
            artifacts=tuple(artifacts),
            collections=(collection,),
            metrics={"artifacts": len(artifacts)},
            started_at=started,
        )


class SearchTemplate:
    """Execute a registered search client and optionally fan out over hits."""

    name = "site.search"
    version = "1"
    input_model = SearchInput

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        started = datetime.now(UTC)
        spec = SearchInput.model_validate(job.payload)
        service = context.require("search")
        search = getattr(service, "search", None)
        if not callable(search):
            raise TypeError("runtime service 'search' must provide async search()")
        result = await search(
            SearchRequest(
                query=spec.query,
                provider=spec.provider,
                limit=spec.limit,
                cursor=spec.cursor,
                filters=spec.filters,
            )
        )
        artifacts = tuple(
            ArtifactRef(
                kind="search_hit",
                source_url=hit.url,
                name=hit.title,
                media_type=hit.media_type,
                metadata={
                    "summary": hit.summary,
                    "score": hit.score,
                    "provider": result.provider,
                    **hit.metadata,
                },
            )
            for hit in result.hits
        )
        collection = ArtifactCollection(
            kind="search_results",
            title=spec.query,
            members=tuple(
                ArtifactMember(artifact=artifact, position=position)
                for position, artifact in enumerate(artifacts)
            ),
            continuation_token=result.next_cursor,
            metadata={"provider": result.provider, **result.metadata},
        )
        spawned = (
            tuple(
                _child(job, spec.visit_template, hit.url, spec.visit_payload) for hit in result.hits
            )
            if spec.visit_template is not None
            else ()
        )
        return JobResult.succeeded(
            job,
            output={
                "provider": result.provider,
                "query": result.query,
                "hit_count": len(result.hits),
                "next_cursor": result.next_cursor,
            },
            artifacts=artifacts,
            collections=(collection,),
            spawned_jobs=spawned,
            metrics={"search_hits": len(result.hits)},
            started_at=started,
        )


def register_builtin_templates(registry: TemplateRegistry) -> None:
    """Register the stable built-in catalog into ``registry``."""
    registry.register(
        PaginationTemplate(),
        description="Discover, enumerate, or follow paginated web pages.",
        category="crawl",
        input_schema=PaginationInput.model_json_schema(),
    )
    registry.register(
        MediaAcquisitionTemplate(),
        description="Acquire media, galleries, playlists, and collections.",
        category="media",
        input_schema=MediaAcquisitionInput.model_json_schema(),
    )
    registry.register(
        SearchTemplate(),
        description="Search through a registered site-specific provider.",
        category="search",
        input_schema=SearchInput.model_json_schema(),
    )


__all__ = [
    "MediaAcquisitionInput",
    "MediaAcquisitionTemplate",
    "PaginationInput",
    "PaginationTemplate",
    "SearchInput",
    "SearchTemplate",
    "register_builtin_templates",
]
