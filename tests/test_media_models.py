"""Canonical media metadata and Pillow processing tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyfetcher.downloaders.base import DownloadResult, MediaInfo
from pyfetcher.media import (
    ImageProcessingSpec,
    MediaMetadata,
    ThumbnailInfo,
    generate_thumbnail,
    inspect_media,
    process_image,
)

Image = pytest.importorskip("PIL.Image")


def test_static_and_animated_image_metadata(tmp_path: Path) -> None:
    png = tmp_path / "image.png"
    Image.new("RGBA", (80, 40), (255, 0, 0, 128)).save(png)
    metadata = inspect_media(png, checksum=True)
    assert metadata.kind == "image"
    assert metadata.mime_type == "image/png"
    assert metadata.image is not None
    assert metadata.image.dimensions.width == 80
    assert metadata.image.has_alpha is True
    assert metadata.checksum_sha256

    gif = tmp_path / "animated.gif"
    frames = [Image.new("RGB", (12, 8), color) for color in ("red", "blue")]
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=[50, 70], loop=0)
    animated = inspect_media(gif)
    assert animated.kind == "animation"
    assert animated.image is not None
    assert animated.image.frame_count == 2
    assert animated.image.total_duration_seconds == pytest.approx(0.12)


def test_image_processing_and_thumbnail_generation(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (120, 60), "green").save(source)
    converted = tmp_path / "converted.webp"
    result = process_image(
        source,
        converted,
        ImageProcessingSpec(width=40, height=40, fit="contain", output_format="WEBP"),
    )
    assert result.metadata.image is not None
    assert result.metadata.image.dimensions.width == 40
    assert result.metadata.image.dimensions.height == 20

    thumbnail_path = tmp_path / "thumb.webp"
    thumbnail = generate_thumbnail(source, thumbnail_path, width=32, height=32)
    assert thumbnail.thumbnail is not None
    assert thumbnail.thumbnail.generated is True
    assert thumbnail.thumbnail.path == str(thumbnail_path)


def test_downloader_models_normalize_metadata_and_streams(tmp_path: Path) -> None:
    info = MediaInfo(
        url="https://example.com/video.mp4",
        title="Video",
        mime_type="video/mp4",
        ext="mp4",
        width=1920,
        height=1080,
        thumbnails=(ThumbnailInfo(url="https://example.com/thumb.jpg"),),
        provider="yt_dlp",
    )
    metadata = info.to_metadata()
    assert metadata.kind == "video"
    assert metadata.primary_thumbnail is not None
    assert metadata.provenance.provider == "yt_dlp"

    path = tmp_path / "video.mp4"
    path.write_bytes(b"video")
    result = DownloadResult(
        source_url=info.url,
        local_path=str(path),
        filename=path.name,
        file_size_bytes=5,
        media_info=info,
    )
    assert result.to_metadata().path == str(path)
    assert result.byte_stream().read() == b"video"


def test_unknown_file_still_returns_typed_hints(tmp_path: Path) -> None:
    path = tmp_path / "payload.unknown"
    path.write_bytes(b"opaque")
    assert isinstance(inspect_media(path), MediaMetadata)
