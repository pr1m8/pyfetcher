"""Typed URL value and pattern tests."""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest
from pydantic import AnyHttpUrl, BaseModel

from pyfetcher.contracts import URL, URLBuildError, URLPattern, URLPatternError, URLTemplate


class GalleryParams(BaseModel):
    gallery_id: int
    page: int = 1


def test_url_adapts_and_manipulates_common_url_values() -> None:
    url = URL(urlsplit("https://example.com/gallery/12?page=1&tag=a&tag=b"))
    assert URL(AnyHttpUrl("https://example.com/path")).path == "/path"
    assert str(url.join("../about")) == "https://example.com/about"
    assert str(url.with_path("other", keep_query=False)) == "https://example.com/other"
    assert url.add_query(page=2, blank=None).query_params == {
        "page": ["2"],
        "tag": ["a", "b"],
        "blank": [""],
    }
    assert str(url.without_query("page")) == "https://example.com/gallery/12?tag=a&tag=b"
    assert str(url.with_fragment("section")).endswith("#section")


def test_url_pattern_matches_validates_and_builds_round_trip() -> None:
    pattern = URLPattern(
        "gallery.page",
        params_model=GalleryParams,
        hosts=("example.com",),
        path=r"/gallery/(?P<gallery_id>\d+)/page/(?P<page>\d+)",
        template="https://example.com/gallery/{gallery_id}/page/{page}",
    )
    match = pattern.match("https://example.com/gallery/42/page/3")
    assert match is not None
    assert match.name == "gallery.page"
    assert match.params == GalleryParams(gallery_id=42, page=3)
    assert pattern.build({"gallery_id": 42, "page": 4}) == URL(
        "https://example.com/gallery/42/page/4"
    )
    assert pattern.match("https://other.example/gallery/42/page/3") is None


def test_url_pattern_can_capture_typed_query_parameters() -> None:
    pattern = URLPattern(
        "gallery.query",
        params_model=GalleryParams,
        hosts=("example.com",),
        path=r"/gallery/(?P<gallery_id>\d+)",
        query={"page": r"\d+"},
    )
    assert pattern.parse("https://example.com/gallery/7?page=5") == GalleryParams(
        gallery_id=7,
        page=5,
    )
    assert pattern.match("https://example.com/gallery/7?page=nope") is None


def test_url_patterns_report_nonmatches_and_nonreversible_patterns() -> None:
    pattern = URLPattern(
        "read.only",
        params_model=GalleryParams,
        path=r"/gallery/(?P<gallery_id>\d+)",
    )
    with pytest.raises(URLPatternError, match="does not match"):
        pattern.parse("https://example.com/nope")
    with pytest.raises(URLBuildError, match="no template"):
        pattern.build({"gallery_id": 1})


def test_explicit_url_template_validates_parameters() -> None:
    template = URLTemplate(
        "https://example.com/gallery/{gallery_id}/page/{page}",
        GalleryParams,
    )
    assert str(template.build({"gallery_id": "8", "page": 2})) == (
        "https://example.com/gallery/8/page/2"
    )


def test_optional_url_tools() -> None:
    pytest.importorskip("w3lib")
    pytest.importorskip("tldextract")
    pytest.importorskip("yarl")
    url = URL("https://www.example.co.uk/path?b=2&a=1#fragment")
    assert str(url.canonicalize()) == "https://www.example.co.uk/path?a=1&b=2"
    assert url.domain_parts().registered_domain == "example.co.uk"
    assert str(url.to_yarl()) == str(url)
    assert len(url.fingerprint()) == 64
