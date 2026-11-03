---
name: gallery-dl-acquire
description: Build, integrate, debug, or document fetchkit image and gallery metadata/download workflows backed by gallery-dl, including extractor configuration, ranges, filenames, archives, cookies, proxies, credential references, progress events, overwrite policy, and provider-native options. Use for specialized gallery acquisition, not ordinary HTTP files or yt-dlp media extractors.
---

# fetchkit gallery-dl Acquire

Use the provider-neutral acquisition API while keeping gallery-dl configuration
inside its own namespace.

## Install and request explicitly

```bash
python -m pip install 'fetchkit[downloaders]'
```

```python
from pyfetcher import AcquisitionRequest, AcquisitionService

request = AcquisitionRequest(
    url="https://imgur.com/a/...",
    provider="gallery_dl",
    operation="download",
    output_dir="images",
    gallery_dl_options={
        "range": "1-25",
        "archive": "gallery.sqlite3",
    },
)

async with AcquisitionService() as service:
    result = await service.acquire(request)
```

Use ``operation="metadata"`` to enumerate provider metadata without a download.
Use an explicit provider for ambiguous hosts; ``auto`` uses host scoring and
records automatic selection in the result provenance.

## Keep options isolated

Place extractor settings, range selection, archive behavior, directory rules,
and gallery-dl filename configuration in ``gallery_dl_options``. Use shared
fields for headers, cookies, proxy, output path, filename template, and
overwrite behavior. Never put yt-dlp formats or postprocessors here.

## Resolve credentials safely

Set ``credential_ref`` and configure an ``AcquisitionService`` resolver that
returns ``AcquisitionCredentials``. Keep passwords and cookie-file paths out of
serialized jobs. Put unavoidable provider-native authentication configuration
in ``AcquisitionCredentials.provider_data``.

## Consume events

Iterate ``service.aiter_events(request)`` to observe progress and each acquired
item. The final ``completed`` event carries the normalized result and provider
provenance. Treat a following raised exception as authoritative after a
``failed`` event.

## Normalize collections and artifacts

Retain gallery-dl extractor data as provider provenance while mapping common
image, gallery, and collection fields into fetchkit's typed document and media
models. Persist downloaded bytes through a ``BlobStore`` and return
``ArtifactRef`` values from durable jobs. Use ``$typed-page-extraction`` for
HTML gallery discovery, ``$media-artifacts`` for inspection or thumbnails, and
``$durable-web-jobs`` for queued gallery templates.

## Test and validate

Use fake gallery-dl jobs/configuration in unit tests. Keep real galleries and
authenticated extractors opt-in.

```bash
pdm run pytest tests/test_acquisition.py tests/test_downloaders_unit.py -q
pdm run ruff check src/ tests/ examples/
```

Use ``$http-fetch`` for direct image URLs and ``$yt-dlp-acquire`` for video or
audio extractor workflows.
