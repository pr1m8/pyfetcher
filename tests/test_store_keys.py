"""Tests for pyfetcher.store.keys module."""

from __future__ import annotations

import re

from pyfetcher.store.keys import _ext_from_mime, generate_media_key


class TestGenerateMediaKey:
    def test_generate_media_key_with_filename(self):
        key = generate_media_key(
            source_url="https://example.com/photo.jpg",
            filename="my photo.jpg",
        )
        assert key.startswith("media/")
        assert ".jpg" in key
        # Should contain a slugified name
        assert "my-photo" in key

    def test_generate_media_key_without_filename(self):
        key = generate_media_key(
            source_url="https://example.com/photo.jpg",
        )
        assert key.startswith("media/")
        # Without filename, should use url hash as name
        # Pattern: media/YYYY/MM/DD/<hash>/<hash>
        parts = key.split("/")
        assert len(parts) == 6  # media / YYYY / MM / DD / hash / name

    def test_generate_media_key_custom_prefix(self):
        key = generate_media_key(
            source_url="https://example.com/file.pdf",
            filename="doc.pdf",
            prefix="documents",
        )
        assert key.startswith("documents/")

    def test_generate_media_key_with_mime_type_fallback(self):
        key = generate_media_key(
            source_url="https://example.com/image",
            mime_type="image/png",
        )
        assert key.endswith(".png")

    def test_generate_media_key_date_in_path(self):
        key = generate_media_key(
            source_url="https://example.com/file.txt",
            filename="file.txt",
        )
        # Should contain a date pattern YYYY/MM/DD
        date_pattern = r"\d{4}/\d{2}/\d{2}"
        assert re.search(date_pattern, key) is not None

    def test_generate_media_key_deterministic_hash(self):
        """Same source_url should produce same hash part."""
        key1 = generate_media_key(
            source_url="https://example.com/file.txt",
            filename="file.txt",
        )
        key2 = generate_media_key(
            source_url="https://example.com/file.txt",
            filename="file.txt",
        )
        # The hash portion should be the same (extract hash from path)
        parts1 = key1.split("/")
        parts2 = key2.split("/")
        assert parts1[4] == parts2[4]  # hash dir should match

    def test_generate_media_key_filename_slug_truncation(self):
        """Long filenames should be truncated via slugify max_length=80."""
        long_name = "a" * 200 + ".jpg"
        key = generate_media_key(
            source_url="https://example.com/long",
            filename=long_name,
        )
        # The slug part should not exceed 80 chars + extension
        name_part = key.split("/")[-1]
        stem = name_part.rsplit(".", 1)[0]
        assert len(stem) <= 80


class TestExtFromMime:
    def test_ext_from_mime_known_jpeg(self):
        assert _ext_from_mime("image/jpeg") == ".jpg"

    def test_ext_from_mime_known_png(self):
        assert _ext_from_mime("image/png") == ".png"

    def test_ext_from_mime_known_mp4(self):
        assert _ext_from_mime("video/mp4") == ".mp4"

    def test_ext_from_mime_known_mp3(self):
        assert _ext_from_mime("audio/mpeg") == ".mp3"

    def test_ext_from_mime_known_pdf(self):
        assert _ext_from_mime("application/pdf") == ".pdf"

    def test_ext_from_mime_unknown(self):
        assert _ext_from_mime("application/octet-stream") == ""

    def test_ext_from_mime_none(self):
        assert _ext_from_mime(None) == ""

    def test_ext_from_mime_with_charset(self):
        """MIME types with charset parameters should still resolve."""
        assert _ext_from_mime("image/jpeg; charset=utf-8") == ".jpg"

    def test_ext_from_mime_known_gif(self):
        assert _ext_from_mime("image/gif") == ".gif"

    def test_ext_from_mime_known_webp(self):
        assert _ext_from_mime("image/webp") == ".webp"

    def test_ext_from_mime_known_webm(self):
        assert _ext_from_mime("video/webm") == ".webm"

    def test_ext_from_mime_known_ogg(self):
        assert _ext_from_mime("audio/ogg") == ".ogg"
