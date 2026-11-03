"""Standard media metadata inspection and image processing."""

from pyfetcher.media.inspect import MediaInspectionError, ainspect_media, inspect_media
from pyfetcher.media.models import (
    AudioStreamInfo,
    ImageInfo,
    ImageProcessingSpec,
    MediaKind,
    MediaMetadata,
    MediaProcessingResult,
    MediaProvenance,
    PixelDimensions,
    ThumbnailInfo,
    VideoStreamInfo,
    media_kind,
)
from pyfetcher.media.process import generate_thumbnail, process_image

__all__ = [
    "AudioStreamInfo",
    "ImageInfo",
    "ImageProcessingSpec",
    "MediaInspectionError",
    "MediaKind",
    "MediaMetadata",
    "MediaProcessingResult",
    "MediaProvenance",
    "PixelDimensions",
    "ThumbnailInfo",
    "VideoStreamInfo",
    "ainspect_media",
    "generate_thumbnail",
    "inspect_media",
    "media_kind",
    "process_image",
]
