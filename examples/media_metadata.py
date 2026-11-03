"""Example: inspect an image and generate a standardized thumbnail.

Run with:
    python examples/media_metadata.py

Requires:
    pip install 'fetchkit[media]'
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

from pyfetcher import generate_thumbnail, inspect_media


def main() -> None:
    """Create local sample media so the example is deterministic and offline."""
    with tempfile.TemporaryDirectory(prefix="fetchkit-media-example-") as directory:
        root = Path(directory)
        source = root / "sample.png"
        thumbnail = root / "sample-thumb.webp"
        Image.new("RGBA", (640, 360), (40, 90, 180, 220)).save(source)

        metadata = inspect_media(source, checksum=True)
        result = generate_thumbnail(source, thumbnail, width=240, height=240)

        print(metadata.model_dump(mode="json", exclude_none=True))
        print(result.thumbnail.model_dump(mode="json", exclude_none=True))


if __name__ == "__main__":
    main()
