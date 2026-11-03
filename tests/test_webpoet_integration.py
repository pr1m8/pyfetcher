from __future__ import annotations

import pytest

web_poet = pytest.importorskip("web_poet")

from pyfetcher.contracts import FetchResponse
from pyfetcher.integrations.webpoet import WebPoetHttpAdapter, WebPoetPageRegistry, WebPoetService


class FakeFetch:
    async def send(self, request):
        return FetchResponse(
            request_url=request.url.unicode_string(),
            final_url=request.url.unicode_string(),
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content_type="text/html; charset=utf-8",
            text="<h1>Hello</h1>",
            body=b"<h1>Hello</h1>",
            backend="fake",
            elapsed_ms=1,
        )


class TitlePage(web_poet.WebPage):
    def to_item(self):
        return {"title": self.css("h1::text").get()}


async def test_webpoet_http_client_uses_fetchkit_downloader() -> None:
    client = WebPoetHttpAdapter(FakeFetch()).http_client()
    response = await client.get("https://example.com")
    assert response.status == 200
    assert response.text == "<h1>Hello</h1>"


async def test_webpoet_service_executes_allowlisted_page() -> None:
    pages = WebPoetPageRegistry()
    pages.register(TitlePage, name="title")
    service = WebPoetService(FakeFetch(), pages=pages)
    item, _ = await service.extract("title", "https://example.com")
    assert item == {"title": "Hello"}
