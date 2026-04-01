"""Structured output models for pyfetcher MCP tools.

Purpose:
    Provide Pydantic models for MCP tool return values, ensuring LLMs
    receive well-structured, typed data from every tool call.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FetchResult(BaseModel):
    """Structured result from fetching a URL."""

    url: str = Field(description="Original request URL")
    final_url: str = Field(description="Final URL after redirects")
    status_code: int = Field(description="HTTP status code")
    ok: bool = Field(description="True for 2xx/3xx status codes")
    content_type: str | None = Field(default=None, description="Response Content-Type")
    headers: dict[str, str] = Field(default_factory=dict, description="Response headers")
    text: str | None = Field(default=None, description="Response body text")
    elapsed_ms: float = Field(description="Request duration in milliseconds")
    backend: str = Field(description="HTTP backend used")


class ScrapeResult(BaseModel):
    """Structured result from CSS selector extraction."""

    url: str = Field(description="Page URL")
    selector: str = Field(description="CSS selector used")
    elements: list[str] = Field(default_factory=list, description="Extracted text content")
    count: int = Field(description="Number of elements found")


class LinkInfo(BaseModel):
    """Single extracted link."""

    url: str = Field(description="Link URL")
    text: str = Field(description="Link text")
    is_external: bool = Field(description="Whether the link is external")


class LinksResult(BaseModel):
    """Structured result from link extraction."""

    url: str = Field(description="Page URL")
    links: list[LinkInfo] = Field(default_factory=list, description="Extracted links")
    total: int = Field(description="Total links found")
    internal: int = Field(description="Internal links count")
    external: int = Field(description="External links count")


class MetadataResult(BaseModel):
    """Structured result from metadata extraction."""

    url: str = Field(description="Page URL")
    title: str | None = Field(default=None, description="Page title")
    description: str | None = Field(default=None, description="Meta description")
    canonical_url: str | None = Field(default=None, description="Canonical URL")
    og_title: str | None = Field(default=None, description="Open Graph title")
    og_description: str | None = Field(default=None, description="Open Graph description")
    og_image: str | None = Field(default=None, description="Open Graph image URL")
    og_type: str | None = Field(default=None, description="Open Graph type")
    favicons: list[str] = Field(default_factory=list, description="Favicon URLs")


class FormInfo(BaseModel):
    """Single extracted form."""

    action: str = Field(description="Form action URL")
    method: str = Field(description="HTTP method")
    fields: dict[str, str] = Field(default_factory=dict, description="Field name -> default value")


class FormsResult(BaseModel):
    """Structured result from form extraction."""

    url: str = Field(description="Page URL")
    forms: list[FormInfo] = Field(default_factory=list, description="Extracted forms")
    count: int = Field(description="Number of forms found")


class TableResult(BaseModel):
    """Structured result from table extraction."""

    url: str = Field(description="Page URL")
    selector: str = Field(description="CSS selector used")
    rows: list[list[str]] = Field(default_factory=list, description="Table rows")
    row_count: int = Field(description="Number of rows")


class RobotsResult(BaseModel):
    """Structured result from robots.txt check."""

    url: str = Field(description="Site URL")
    path: str = Field(description="Path checked")
    user_agent: str = Field(description="User-agent checked")
    allowed: bool = Field(description="Whether the path is allowed")
    sitemaps: list[str] = Field(default_factory=list, description="Sitemap URLs found")


class SitemapResult(BaseModel):
    """Structured result from sitemap parsing."""

    url: str = Field(description="Sitemap URL")
    entries: list[dict[str, str | None]] = Field(
        default_factory=list, description="Sitemap entries with loc, lastmod, priority"
    )
    count: int = Field(description="Number of entries")


class HeadersResult(BaseModel):
    """Structured result from header generation."""

    profile: str = Field(description="Browser profile used")
    headers: dict[str, str] = Field(default_factory=dict, description="Generated headers")


class ProfileInfo(BaseModel):
    """Browser profile information."""

    name: str = Field(description="Profile name")
    browser: str = Field(description="Browser family")
    platform: str = Field(description="Operating system")
    mobile: bool = Field(description="Whether this is a mobile profile")


class ArticleResult(BaseModel):
    """Structured result from article extraction."""

    url: str = Field(description="Article URL")
    text: str | None = Field(default=None, description="Extracted article text")
    markdown: str | None = Field(default=None, description="Markdown conversion")
    title: str | None = Field(default=None, description="Article title")


class DownloadResult(BaseModel):
    """Structured result from file download."""

    url: str = Field(description="Source URL")
    path: str = Field(description="Local file path")
    size_bytes: int = Field(description="File size in bytes")
    checksum_sha256: str | None = Field(default=None, description="SHA-256 checksum")
