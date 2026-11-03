---
name: media-artifacts
description: Build, integrate, debug, or document fetchkit ByteStream, MediaMetadata, image or video inspection, dimensions, duration, thumbnails, image processing, BlobStore, BlobRef, ArtifactRef, checksums, provenance, or provider metadata normalization. Use after or around acquisition; use yt-dlp or gallery-dl skills for provider-native downloading.
---

# fetchkit Media and Artifacts

Normalize media and large content without tying downstream code to a downloader
or storage backend.

## Normalize byte sources

Use ``ByteStream`` for bytes, files, sync iterables, or async iterables that
need one bounded interface. Call the explicit sync or async read method for the
current execution context. Set maximum byte limits for untrusted input and do
not assume a one-shot generator is replayable.

## Inspect and process media

Use canonical ``MediaMetadata`` for reusable format, MIME type, size,
dimensions, duration, frame, codec, thumbnail, and provenance fields. Keep
provider-native metadata alongside the normalized view when it is useful.

Use the media inspection and image-processing helpers for local or bounded
content. Make output format, dimensions, aspect behavior, quality, and animated
image handling explicit. Keep processor dependencies optional and report the
extra required when unavailable.

## Persist artifacts

Write large content to a ``BlobStore`` and move ``BlobRef`` or ``ArtifactRef``
through jobs and queues. Preserve content type, byte count, checksum, source
URL, provider, and transformation provenance. Do not place raw bytes, open file
handles, or provider objects in serialized job messages.

## Validate media behavior

Use generated, local fixtures rather than remote media. Cover corrupt input,
size bounds, sync/async sources, animated formats, metadata normalization, and
blob integrity.

```bash
pdm run pytest tests/test_media_models.py tests/test_streams_and_extraction.py -q
pdm run pytest tests/test_jobs.py -q
pdm run ruff check src/ tests/ examples/
```

Read ``docs/api/media.rst``, ``docs/durable-flows.rst``, and
``examples/media_metadata.py`` before changing contracts. Use
``$yt-dlp-acquire`` or ``$gallery-dl-acquire`` for specialized acquisition and
``$durable-web-jobs`` for queued processing.
