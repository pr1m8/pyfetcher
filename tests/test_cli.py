"""CLI tests using click.testing.CliRunner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from pyfetcher.cli.app import cli
from pyfetcher.contracts.response import FetchResponse

# The CLI commands use lazy imports inside each function body, so we must
# patch at the source module path, not at pyfetcher.cli.app.
_FETCH_SERVICE_PATH = "pyfetcher.fetch.service.FetchService"
_DOWNLOAD_SERVICE_PATH = "pyfetcher.download.service.DownloadService"


def _make_mock_response(
    *,
    text: str = "<html><head><title>Test</title></head><body><h1>Hello</h1><p>World</p></body></html>",
    status_code: int = 200,
    content_type: str = "text/html",
) -> FetchResponse:
    """Build a mock FetchResponse for CLI tests."""
    return FetchResponse(
        request_url="https://example.com/",
        final_url="https://example.com/",
        status_code=status_code,
        headers={"content-type": content_type},
        content_type=content_type,
        text=text,
        body=text.encode() if text else b"",
        backend="httpx",
        elapsed_ms=42.0,
    )


# ---------------------------------------------------------------------------
# Top-level help
# ---------------------------------------------------------------------------


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "pyfetcher" in result.output
    assert "fetch" in result.output
    assert "headers" in result.output
    assert "scrape" in result.output


# ---------------------------------------------------------------------------
# headers command
# ---------------------------------------------------------------------------


def test_headers_list():
    runner = CliRunner()
    result = runner.invoke(cli, ["headers", "--list"])
    assert result.exit_code == 0
    assert "chrome_win" in result.output
    assert "firefox_win" in result.output


def test_headers_profile_json():
    runner = CliRunner()
    result = runner.invoke(cli, ["headers", "--profile", "chrome_win", "-o", "json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "user-agent" in parsed
    assert "Mozilla" in parsed["user-agent"]


def test_headers_profile_raw():
    runner = CliRunner()
    result = runner.invoke(cli, ["headers", "--profile", "chrome_win", "-o", "raw"])
    assert result.exit_code == 0
    assert "user-agent:" in result.output
    assert "accept:" in result.output


# ---------------------------------------------------------------------------
# user-agent command
# ---------------------------------------------------------------------------


def test_user_agent_basic():
    runner = CliRunner()
    result = runner.invoke(cli, ["user-agent"])
    assert result.exit_code == 0
    assert "Mozilla" in result.output


def test_user_agent_browser_filter():
    runner = CliRunner()
    result = runner.invoke(cli, ["user-agent", "--browser", "chrome"])
    assert result.exit_code == 0
    assert "Chrome" in result.output


def test_user_agent_count():
    runner = CliRunner()
    result = runner.invoke(cli, ["user-agent", "--count", "3"])
    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line.strip()]
    assert len(lines) == 3


# ---------------------------------------------------------------------------
# fetch command (mocked network)
# ---------------------------------------------------------------------------


def test_fetch_json_output():
    mock_response = _make_mock_response()
    with patch(_FETCH_SERVICE_PATH) as MockService:
        instance = MockService.return_value
        instance.fetch.return_value = mock_response
        instance.close = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["fetch", "https://example.com", "-o", "json"])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        assert parsed["status_code"] == 200
        assert parsed["ok"] is True
        assert parsed["request_url"] == "https://example.com/"
        instance.close.assert_called()


def test_fetch_raw_output():
    mock_response = _make_mock_response(text="<html>raw body</html>")
    with patch(_FETCH_SERVICE_PATH) as MockService:
        instance = MockService.return_value
        instance.fetch.return_value = mock_response
        instance.close = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["fetch", "https://example.com", "-o", "raw"])
        assert result.exit_code == 0, result.output
        assert "raw body" in result.output


def test_fetch_headers_output():
    mock_response = _make_mock_response()
    with patch(_FETCH_SERVICE_PATH) as MockService:
        instance = MockService.return_value
        instance.fetch.return_value = mock_response
        instance.close = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["fetch", "https://example.com", "-o", "headers"])
        assert result.exit_code == 0, result.output
        assert "content-type: text/html" in result.output


# ---------------------------------------------------------------------------
# scrape command (mocked network)
# ---------------------------------------------------------------------------

_SCRAPE_HTML = (
    "<html><head><title>Test Page</title>"
    '<meta name="description" content="A test page" />'
    '<meta property="og:title" content="OG Test" />'
    '<meta property="og:image" content="https://example.com/img.png" />'
    "</head><body>"
    "<h1>Main Title</h1>"
    "<p>First paragraph.</p>"
    '<a href="/about">About</a>'
    '<a href="https://external.com">External</a>'
    "</body></html>"
)


def _patch_scrape_service(html: str = _SCRAPE_HTML):
    """Return a context manager that patches FetchService for scrape tests."""
    mock_response = _make_mock_response(text=html)
    return patch(
        _FETCH_SERVICE_PATH,
        **{
            "return_value.fetch.return_value": mock_response,
            "return_value.close": MagicMock(),
        },
    )


def test_scrape_css():
    with _patch_scrape_service():
        runner = CliRunner()
        result = runner.invoke(cli, ["scrape", "https://example.com", "--css", "h1"])
        assert result.exit_code == 0, result.output
        assert "Main Title" in result.output


def test_scrape_css_json():
    with _patch_scrape_service():
        runner = CliRunner()
        result = runner.invoke(cli, ["scrape", "https://example.com", "--css", "h1", "-o", "json"])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        assert "Main Title" in parsed


def test_scrape_links():
    with _patch_scrape_service():
        runner = CliRunner()
        result = runner.invoke(cli, ["scrape", "https://example.com", "--links"])
        assert result.exit_code == 0, result.output
        assert "About" in result.output
        assert "External" in result.output


def test_scrape_links_json():
    with _patch_scrape_service():
        runner = CliRunner()
        result = runner.invoke(cli, ["scrape", "https://example.com", "--links", "-o", "json"])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        urls = [item["url"] for item in parsed]
        assert any("/about" in u for u in urls)


def test_scrape_text():
    with _patch_scrape_service():
        runner = CliRunner()
        result = runner.invoke(cli, ["scrape", "https://example.com", "--text"])
        assert result.exit_code == 0, result.output
        assert "Main Title" in result.output
        assert "First paragraph" in result.output


def test_scrape_meta():
    with _patch_scrape_service():
        runner = CliRunner()
        result = runner.invoke(cli, ["scrape", "https://example.com", "--meta"])
        assert result.exit_code == 0, result.output
        assert "Test Page" in result.output


def test_scrape_meta_json():
    with _patch_scrape_service():
        runner = CliRunner()
        result = runner.invoke(cli, ["scrape", "https://example.com", "--meta", "-o", "json"])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        assert parsed["title"] == "Test Page"
        assert parsed["open_graph"]["title"] == "OG Test"


# ---------------------------------------------------------------------------
# robots command (mocked network)
# ---------------------------------------------------------------------------


def test_robots_allowed():
    robots_text = "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml"
    mock_response = _make_mock_response(text=robots_text, content_type="text/plain")
    with patch(_FETCH_SERVICE_PATH) as MockService:
        instance = MockService.return_value
        instance.fetch.return_value = mock_response
        instance.close = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["robots", "https://example.com"])
        assert result.exit_code == 0, result.output
        assert "ALLOWED" in result.output


def test_robots_disallowed():
    robots_text = "User-agent: *\nDisallow: /admin"
    mock_response = _make_mock_response(text=robots_text, content_type="text/plain")
    with patch(_FETCH_SERVICE_PATH) as MockService:
        instance = MockService.return_value
        instance.fetch.return_value = mock_response
        instance.close = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["robots", "https://example.com", "-p", "/admin"])
        assert result.exit_code == 0, result.output
        assert "DISALLOWED" in result.output


# ---------------------------------------------------------------------------
# download command (mocked network)
# ---------------------------------------------------------------------------


def test_download_command():
    with patch(_FETCH_SERVICE_PATH), patch(_DOWNLOAD_SERVICE_PATH) as MockDL:
        mock_dl_instance = MockDL.return_value

        async def fake_download(req, dest):
            return Path(dest)

        mock_dl_instance.adownload_to_path = fake_download

        runner = CliRunner()
        result = runner.invoke(cli, ["download", "https://example.com/file.pdf", "/tmp/file.pdf"])
        assert result.exit_code == 0, result.output
        assert "Downloaded" in result.output


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_fetch_error_shows_message():
    with patch(_FETCH_SERVICE_PATH) as MockService:
        instance = MockService.return_value
        instance.fetch.side_effect = ConnectionError("Connection refused")
        instance.close = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["fetch", "https://example.com", "-o", "json"])
        assert result.exit_code == 1
        assert "Error" in result.output or "Connection refused" in result.output
