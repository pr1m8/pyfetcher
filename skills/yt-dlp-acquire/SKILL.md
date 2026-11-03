---
name: yt-dlp-acquire
description: Build, integrate, debug, or document fetchkit video and audio metadata/download workflows backed by yt-dlp, including extractor selection, format expressions, playlists, subtitles, postprocessors, proxies, credential references, filenames, progress events, retries, and provider-native options. Use for specialized media acquisition, not ordinary HTTP files or gallery-dl extractors.
---

# fetchkit yt-dlp Acquire

Use the provider-neutral acquisition API while preserving yt-dlp escape hatches.

## Install and request explicitly

```bash
python -m pip install 'fetchkit[downloaders]'
```

```python
from pyfetcher import AcquisitionRequest, AcquisitionService

request = AcquisitionRequest(
    url="https://www.youtube.com/watch?v=...",
    provider="yt_dlp",
    operation="download",
    output_dir="media",
    filename_template="%(title)s-%(id)s.%(ext)s",
    yt_dlp_options={
        "format": "bestvideo+bestaudio/best",
        "noplaylist": True,
    },
)

async with AcquisitionService() as service:
    result = await service.acquire(request)
```

Use ``operation="metadata"`` to extract information without downloading.
Choose ``provider="yt_dlp"`` explicitly for ambiguous URLs; ``auto`` uses host
scoring and records selection in ``result.provenance``.

## Keep options isolated

Place only yt-dlp-native values in ``yt_dlp_options``: formats, playlists,
subtitles, postprocessors, extractor arguments, and output templates. Use
shared fields for headers, proxy, timeout, retries, overwrite, and output path.
Never put gallery-dl configuration in this dictionary.

## Resolve credentials by reference

Store ``credential_ref`` on the request and give ``AcquisitionService`` a
``credential_resolver`` returning ``AcquisitionCredentials``. Do not serialize
passwords or cookies into queued requests. Provider data may include native
yt-dlp credential options when necessary.

## Monitor progress

Use ``service.aiter_events(request)`` for ``started``, ``progress``, ``item``,
``completed``, and ``failed`` events. A failed event is followed by the raised
provider error. Cancellation stops the async task, but a provider thread may
need to reach its next yt-dlp cancellation boundary.

## Normalize durable outputs

Preserve provider-native data in the acquisition result, but project reusable
fields into canonical ``MediaMetadata`` and provenance records. When a job
must retain downloaded content, store it through a ``BlobStore`` and pass an
``ArtifactRef`` rather than file bytes or provider objects. Use
``$media-artifacts`` for inspection and thumbnails, and ``$durable-web-jobs``
for queued acquisition templates.

## Test and validate

Mock ``YtdlpDownloader`` or yt-dlp info dictionaries in unit tests. Do not
download real media in the default suite.

```bash
pdm run pytest tests/test_acquisition.py tests/test_downloaders_unit.py -q
pdm run ruff check src/ tests/ examples/
```

Use ``$http-fetch`` for direct file URLs and ``$gallery-dl-acquire`` for image
gallery extractors.
