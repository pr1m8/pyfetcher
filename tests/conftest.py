"""Shared test fixtures for pyfetcher."""

from __future__ import annotations

import pytest

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.contracts.response import FetchResponse


@pytest.fixture
def sample_url() -> str:
    return "https://example.com"


@pytest.fixture
def sample_request(sample_url: str) -> FetchRequest:
    return FetchRequest(url=sample_url)


@pytest.fixture
def sample_response() -> FetchResponse:
    return FetchResponse(
        request_url="https://example.com/",
        final_url="https://example.com/",
        status_code=200,
        headers={"content-type": "text/html"},
        content_type="text/html",
        text="<html><head><title>Example</title></head><body><p>Hello</p></body></html>",
        body=b"<html><head><title>Example</title></head><body><p>Hello</p></body></html>",
        backend="httpx",
        elapsed_ms=42.0,
    )


@pytest.fixture
def sample_html() -> str:
    return """<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <meta name="description" content="A test page" />
    <meta property="og:title" content="OG Test" />
    <meta property="og:description" content="OG Description" />
    <meta property="og:image" content="https://example.com/image.png" />
    <link rel="canonical" href="https://example.com/canonical" />
    <link rel="icon" href="/favicon.ico" />
    <link rel="apple-touch-icon" href="/apple-icon.png" sizes="180x180" />
</head>
<body>
    <nav><a href="/">Home</a></nav>
    <h1>Main Title</h1>
    <p>First paragraph.</p>
    <p>Second paragraph.</p>
    <div class="content">
        <a href="/about">About</a>
        <a href="https://external.com">External</a>
        <a href="#section">Fragment</a>
    </div>
    <form action="/search" method="GET">
        <input type="text" name="q" value="" />
        <input type="hidden" name="lang" value="en" />
        <select name="sort">
            <option value="relevance">Relevance</option>
            <option value="date" selected>Date</option>
        </select>
        <button type="submit">Search</button>
    </form>
    <form action="/login" method="POST" id="login-form">
        <input type="text" name="username" value="" />
        <input type="password" name="password" value="" />
        <textarea name="notes">Default notes</textarea>
    </form>
    <table>
        <tr><th>Name</th><th>Age</th></tr>
        <tr><td>Alice</td><td>30</td></tr>
        <tr><td>Bob</td><td>25</td></tr>
    </table>
    <script>var x = 1;</script>
    <footer>Footer content</footer>
</body>
</html>"""
