"""CLI application for pyfetcher.

Purpose:
    Provide a ``click``-based command-line interface for common pyfetcher
    operations including fetching URLs, scraping content, previewing
    browser headers, batch fetching, and downloading files.

Design:
    - Commands are organized under a main ``pyfetcher`` group.
    - Output formats include JSON, table (Rich), and raw text.
    - Async operations are run via ``asyncio.run``.
    - Error handling provides helpful messages without tracebacks by default.

Examples:
    ::

        $ pyfetcher fetch https://example.com
        $ pyfetcher headers --profile chrome_win
        $ pyfetcher scrape https://example.com --css "h1"
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click


@click.group()
@click.version_option(package_name="fetchkit")
def cli() -> None:
    """pyfetcher - Advanced web fetching and scraping toolkit.

    Fetch URLs, scrape content, generate realistic browser headers,
    and more from the command line.
    """


@cli.command()
@click.argument("url")
@click.option("--method", "-m", default="GET", help="HTTP method.")
@click.option("--header", "-H", multiple=True, help="Custom header (Name: Value).")
@click.option("--data", "-d", default=None, help="Request body data.")
@click.option(
    "--backend",
    "-b",
    default="httpx",
    help="HTTP backend (httpx, aiohttp, curl_cffi, cloudscraper).",
)
@click.option("--profile", "-p", default="chrome_win", help="Browser profile for headers.")
@click.option("--no-verify", is_flag=True, help="Disable SSL verification.")
@click.option("--follow/--no-follow", default=True, help="Follow redirects.")
@click.option(
    "--output", "-o", type=click.Choice(["json", "table", "raw", "headers"]), default="table"
)
@click.option("--timeout", "-t", default=30.0, type=float, help="Total timeout in seconds.")
@click.option("--proxy", default=None, help="HTTP(S) proxy URL.")
def fetch(
    url: str,
    method: str,
    header: tuple[str, ...],
    data: str | None,
    backend: str,
    profile: str,
    no_verify: bool,
    follow: bool,
    output: str,
    timeout: float,
    proxy: str | None,
) -> None:
    """Fetch a URL and display the response.

    Examples:

        pyfetcher fetch https://example.com

        pyfetcher fetch https://api.example.com/data -m POST -d '{"key": "value"}'

        pyfetcher fetch https://example.com -o json
    """
    from pyfetcher.contracts.policy import TimeoutPolicy
    from pyfetcher.contracts.request import FetchRequest
    from pyfetcher.fetch.service import FetchService
    from pyfetcher.headers.browser import BrowserHeaderProvider

    custom_headers: dict[str, str] = {}
    for h in header:
        if ":" in h:
            key, _, val = h.partition(":")
            custom_headers[key.strip()] = val.strip()

    request = FetchRequest(
        url=url,
        method=method.upper(),  # type: ignore[arg-type]
        headers=custom_headers,
        data=data.encode() if data else None,
        backend=backend,  # type: ignore[arg-type]
        verify_ssl=not no_verify,
        allow_redirects=follow,
        timeout=TimeoutPolicy(total_seconds=timeout),
        proxy=proxy,
    )

    service = FetchService(header_provider=BrowserHeaderProvider(profile))

    try:
        response = service.fetch(request)
    except Exception as exc:
        click.secho(f"Error: {exc}", fg="red", err=True)
        sys.exit(1)
    finally:
        service.close()

    if output == "json":
        result = {
            "request_url": response.request_url,
            "final_url": response.final_url,
            "status_code": response.status_code,
            "headers": response.headers,
            "content_type": response.content_type,
            "elapsed_ms": response.elapsed_ms,
            "ok": response.ok,
        }
        click.echo(json.dumps(result, indent=2))
    elif output == "raw":
        if response.text:
            click.echo(response.text)
    elif output == "headers":
        for key, val in response.headers.items():
            click.echo(f"{key}: {val}")
    else:
        try:
            from rich.console import Console

            from pyfetcher.rich import render_fetch_response_table

            console = Console()
            console.print(render_fetch_response_table(response))
        except ImportError:
            click.echo(f"Status: {response.status_code}")
            click.echo(f"URL: {response.final_url}")
            click.echo(f"Elapsed: {response.elapsed_ms:.1f}ms")
            click.echo(f"Content-Type: {response.content_type or 'N/A'}")


def _provider_options(values: tuple[str, ...]) -> dict[str, object]:
    """Parse repeated NAME=JSON provider-native CLI options."""
    parsed: dict[str, object] = {}
    for value in values:
        name, separator, raw = value.partition("=")
        if not separator or not name.strip():
            raise click.BadParameter("provider options must use NAME=VALUE")
        try:
            parsed[name.strip()] = json.loads(raw)
        except json.JSONDecodeError:
            parsed[name.strip()] = raw
    return parsed


@cli.command()
@click.argument("url")
@click.option(
    "--provider",
    "-p",
    default="auto",
    show_default=True,
    help="Built-in or registered provider name.",
)
@click.option("--metadata", is_flag=True, help="Extract metadata without downloading.")
@click.option("--output-dir", "-d", type=click.Path(), default=None)
@click.option("--header", "-H", multiple=True, help="Shared header (Name: Value).")
@click.option("--proxy", default=None, help="Shared provider proxy URL.")
@click.option(
    "--provider-option",
    "provider_options",
    multiple=True,
    help="Provider-native NAME=JSON option; repeat as needed.",
)
@click.option(
    "--load-provider-plugins",
    is_flag=True,
    help="Load installed fetchkit.acquisition.providers entry points.",
)
@click.option("--events", is_flag=True, help="Emit JSON Lines progress events.")
def acquire(
    url: str,
    provider: str,
    metadata: bool,
    output_dir: str | None,
    header: tuple[str, ...],
    proxy: str | None,
    provider_options: tuple[str, ...],
    load_provider_plugins: bool,
    events: bool,
) -> None:
    """Acquire metadata, files, media, or galleries through a provider."""
    from pyfetcher.acquisition import AcquisitionRequest, AcquisitionService

    headers: dict[str, str] = {}
    for value in header:
        name, separator, header_value = value.partition(":")
        if not separator or not name.strip():
            raise click.BadParameter("headers must use 'Name: Value'", param_hint="--header")
        headers[name.strip()] = header_value.strip()

    normalized_provider = provider.replace("-", "_")
    native_options = _provider_options(provider_options)
    if native_options and normalized_provider == "auto":
        raise click.UsageError("--provider-option requires an explicit --provider")
    request = AcquisitionRequest(
        url=url,
        provider=normalized_provider,
        operation="metadata" if metadata else "download",
        output_dir=output_dir,
        headers=headers,
        proxy=proxy,
        provider_options=({normalized_provider: native_options} if native_options else {}),
    )

    async def run() -> None:
        async with AcquisitionService() as service:
            if load_provider_plugins:
                service.load_entry_points()
            if events:
                async for event in service.aiter_events(request):
                    click.echo(event.model_dump_json())
                return
            result = await service.acquire(request)
            click.echo(result.model_dump_json(indent=2))

    try:
        asyncio.run(run())
    except Exception as exc:
        click.secho(f"Error: {exc}", fg="red", err=True)
        raise click.Abort() from exc


@cli.command()
@click.option("--profile", "-p", default=None, help="Specific profile name.")
@click.option(
    "--browser", "-b", default=None, help="Filter by browser (chrome, firefox, safari, edge)."
)
@click.option("--platform", default=None, help="Filter by platform (Windows, macOS, Linux).")
@click.option("--list", "list_all", is_flag=True, help="List all available profiles.")
@click.option("--output", "-o", type=click.Choice(["json", "table", "raw"]), default="table")
def headers(
    profile: str | None,
    browser: str | None,
    platform: str | None,
    list_all: bool,
    output: str,
) -> None:
    """Preview generated browser headers.

    Examples:

        pyfetcher headers --profile chrome_win

        pyfetcher headers --browser firefox -o json

        pyfetcher headers --list
    """
    from pyfetcher.headers.profiles import list_profiles

    if list_all:
        profiles = list_profiles()
        for name in profiles:
            click.echo(name)
        return

    if profile:
        from pyfetcher.headers.browser import get_best_browser_headers

        hdrs = get_best_browser_headers(profile)
    else:
        from pyfetcher.headers.ua import random_profile

        p = random_profile(browser=browser, platform=platform)
        from pyfetcher.headers.browser import get_best_browser_headers

        hdrs = get_best_browser_headers(p.name)

    if output == "json":
        click.echo(json.dumps(hdrs, indent=2))
    elif output == "raw":
        for key, val in hdrs.items():
            click.echo(f"{key}: {val}")
    else:
        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(title="Generated Headers")
            table.add_column("Header", style="cyan")
            table.add_column("Value", style="green")
            for key, val in hdrs.items():
                table.add_row(key, val)
            console.print(table)
        except ImportError:
            for key, val in hdrs.items():
                click.echo(f"{key}: {val}")


@cli.command()
@click.argument("url")
@click.option("--css", "-c", default=None, help="CSS selector to extract.")
@click.option("--text", "-t", is_flag=True, help="Extract readable text only.")
@click.option("--links", "-l", is_flag=True, help="Extract all links.")
@click.option("--forms", "-f", is_flag=True, help="Extract forms.")
@click.option("--meta", is_flag=True, help="Extract page metadata.")
@click.option("--profile", "-p", default="chrome_win", help="Browser profile.")
@click.option("--output", "-o", type=click.Choice(["json", "text"]), default="text")
def scrape(
    url: str,
    css: str | None,
    text: bool,
    links: bool,
    forms: bool,
    meta: bool,
    profile: str,
    output: str,
) -> None:
    """Scrape content from a URL.

    Examples:

        pyfetcher scrape https://example.com --css "h1"

        pyfetcher scrape https://example.com --links -o json

        pyfetcher scrape https://example.com --text

        pyfetcher scrape https://example.com --meta
    """
    from pyfetcher.contracts.request import FetchRequest
    from pyfetcher.fetch.service import FetchService
    from pyfetcher.headers.browser import BrowserHeaderProvider

    service = FetchService(header_provider=BrowserHeaderProvider(profile))
    try:
        response = service.fetch(FetchRequest(url=url))
    except Exception as exc:
        click.secho(f"Error fetching {url}: {exc}", fg="red", err=True)
        sys.exit(1)
    finally:
        service.close()

    html = response.text or ""

    if css:
        from pyfetcher.scrape.selectors import extract_text

        results = extract_text(html, css)
        if output == "json":
            click.echo(json.dumps(results, indent=2))
        else:
            for item in results:
                click.echo(item)

    elif text:
        from pyfetcher.scrape.content import extract_readable_text

        content = extract_readable_text(html)
        click.echo(content)

    elif links:
        from pyfetcher.scrape.links import extract_links

        found = extract_links(html, base_url=url)
        if output == "json":
            click.echo(
                json.dumps(
                    [
                        {"url": lnk.url, "text": lnk.text, "external": lnk.is_external}
                        for lnk in found
                    ],
                    indent=2,
                )
            )
        else:
            for link in found:
                marker = "[ext]" if link.is_external else "[int]"
                click.echo(f"{marker} {link.url}  {link.text}")

    elif forms:
        from pyfetcher.scrape.forms import extract_forms

        found_forms = extract_forms(html, base_url=url)
        if output == "json":
            click.echo(
                json.dumps(
                    [
                        {"action": f.action, "method": f.method, "fields": f.to_dict()}
                        for f in found_forms
                    ],
                    indent=2,
                )
            )
        else:
            for form in found_forms:
                click.echo(f"[{form.method}] {form.action}")
                for field in form.fields:
                    click.echo(f"  {field.name} ({field.type}): {field.value}")

    elif meta:
        from pyfetcher.metadata.html import extract_basic_html_metadata
        from pyfetcher.metadata.opengraph import extract_open_graph_metadata

        metadata = extract_basic_html_metadata(html, base_url=url)
        og = extract_open_graph_metadata(html)
        result = metadata.model_dump()
        if og:
            result["open_graph"] = og.model_dump()
        if output == "json":
            click.echo(json.dumps(result, indent=2, default=str))
        else:
            click.echo(f"Title: {metadata.title or 'N/A'}")
            click.echo(f"Description: {metadata.description or 'N/A'}")
            click.echo(f"Canonical: {metadata.canonical_url or 'N/A'}")
            if og:
                click.echo(f"OG Title: {og.title or 'N/A'}")
                click.echo(f"OG Image: {og.image or 'N/A'}")

    else:
        click.echo(html)


@cli.command()
@click.argument("url")
@click.argument("dest", type=click.Path())
@click.option("--profile", "-p", default="chrome_win", help="Browser profile.")
def download(url: str, dest: str, profile: str) -> None:
    """Download a file from a URL.

    Examples:

        pyfetcher download https://example.com/file.pdf ./file.pdf
    """
    from pyfetcher.contracts.request import FetchRequest
    from pyfetcher.download.service import DownloadService
    from pyfetcher.fetch.service import FetchService
    from pyfetcher.headers.browser import BrowserHeaderProvider

    service = FetchService(header_provider=BrowserHeaderProvider(profile))
    dl = DownloadService(fetch_service=service)

    try:
        path = asyncio.run(dl.adownload_to_path(FetchRequest(url=url), dest))
        click.secho(f"Downloaded to {path}", fg="green")
    except Exception as exc:
        click.secho(f"Error: {exc}", fg="red", err=True)
        sys.exit(1)


@cli.command(name="user-agent")
@click.option("--browser", "-b", default=None, help="Filter by browser.")
@click.option("--platform", "-p", default=None, help="Filter by platform.")
@click.option("--mobile", is_flag=True, default=False, help="Mobile user-agent only.")
@click.option("--count", "-n", default=1, type=int, help="Number of user-agents to generate.")
def user_agent(browser: str | None, platform: str | None, mobile: bool, count: int) -> None:
    """Generate random user-agent strings.

    Examples:

        pyfetcher user-agent

        pyfetcher user-agent --browser chrome --count 5

        pyfetcher user-agent --mobile
    """
    from pyfetcher.headers.ua import random_user_agent

    mobile_flag = True if mobile else None
    for _ in range(count):
        ua = random_user_agent(browser=browser, platform=platform, mobile=mobile_flag)
        click.echo(ua)


@cli.command()
@click.argument("url")
@click.option("--user-agent", "-u", default="*", help="User-agent to check.")
@click.option("--path", "-p", default="/", help="Path to check.")
@click.option("--profile", default="chrome_win", help="Browser profile for fetching.")
def robots(url: str, user_agent: str, path: str, profile: str) -> None:
    """Check robots.txt for a URL.

    Examples:

        pyfetcher robots https://example.com

        pyfetcher robots https://example.com -p /admin -u Googlebot
    """
    from pyfetcher.contracts.request import FetchRequest
    from pyfetcher.fetch.service import FetchService
    from pyfetcher.headers.browser import BrowserHeaderProvider
    from pyfetcher.scrape.robots import is_allowed, parse_robots_txt

    robots_url = url.rstrip("/") + "/robots.txt"
    service = FetchService(header_provider=BrowserHeaderProvider(profile))

    try:
        response = service.fetch(FetchRequest(url=robots_url))
    except Exception as exc:
        click.secho(f"Error fetching robots.txt: {exc}", fg="red", err=True)
        sys.exit(1)
    finally:
        service.close()

    if not response.text:
        click.echo("No robots.txt content found.")
        return

    rules = parse_robots_txt(response.text)
    allowed = is_allowed(rules, path, user_agent=user_agent)

    if allowed:
        click.secho(f"ALLOWED: {path} for {user_agent}", fg="green")
    else:
        click.secho(f"DISALLOWED: {path} for {user_agent}", fg="red")

    if rules.sitemaps:
        click.echo("\nSitemaps:")
        for sitemap in rules.sitemaps:
            click.echo(f"  {sitemap}")


@cli.group()
def templates() -> None:
    """Inspect and validate reusable job-template contracts."""


def _builtin_registry():
    from pyfetcher.jobs import TemplateRegistry, register_builtin_templates

    registry = TemplateRegistry()
    register_builtin_templates(registry)
    return registry


@templates.command(name="list")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
def templates_list(output: str) -> None:
    """List the built-in versioned job-template catalog."""
    descriptors = _builtin_registry().descriptors()
    if output == "json":
        click.echo(
            json.dumps(
                [
                    {
                        "template": descriptor.ref.key,
                        "category": descriptor.category,
                        "description": descriptor.description,
                        "input_schema": descriptor.input_schema,
                    }
                    for descriptor in descriptors
                ],
                indent=2,
            )
        )
        return
    try:
        from rich.console import Console
        from rich.table import Table

        table = Table(title="fetchkit job templates")
        table.add_column("Template")
        table.add_column("Category")
        table.add_column("Description")
        for descriptor in descriptors:
            table.add_row(descriptor.ref.key, descriptor.category, descriptor.description)
        Console().print(table)
    except ImportError:  # pragma: no cover - Rich is a core dependency
        for descriptor in descriptors:
            click.echo(f"{descriptor.ref.key}\t{descriptor.category}\t{descriptor.description}")


@templates.command(name="validate")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def templates_validate(path: Path) -> None:
    """Validate a serialized JobRequest or FlowRequest JSON file."""
    from pydantic import ValidationError

    from pyfetcher.jobs import FlowRequest, JobRequest

    try:
        value = json.loads(path.read_text())
        jobs = (
            FlowRequest.model_validate(value).jobs
            if "jobs" in value
            else (JobRequest.model_validate(value),)
        )
        registry = _builtin_registry()
        for job in jobs:
            registry.validate_payload(job.template, job.payload)
    except (json.JSONDecodeError, KeyError, TypeError, ValidationError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.secho(f"Valid: {len(jobs)} job(s)", fg="green")


@cli.group()
def contracts() -> None:
    """Inspect and export versioned cross-language contracts."""


def _protocol_catalog(*, load_provider_plugins: bool = False):
    from pyfetcher.protocol import discover_protocol_catalog

    return asyncio.run(discover_protocol_catalog(load_provider_plugins=load_provider_plugins))


@contracts.command(name="list")
@click.option("--category", default=None, help="Filter by contract category.")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--load-provider-plugins",
    is_flag=True,
    help="Include installed fetchkit acquisition-provider entry points.",
)
def contracts_list(
    category: str | None,
    output: str,
    load_provider_plugins: bool,
) -> None:
    """List stable JSON Schema contract identifiers."""
    try:
        catalog = _protocol_catalog(load_provider_plugins=load_provider_plugins)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    schemas = tuple(
        item for item in catalog.schemas if category is None or item.category == category
    )
    if output == "json":
        click.echo(
            json.dumps(
                [
                    {
                        "key": item.key,
                        "category": item.category,
                        "role": item.role,
                        "title": item.title,
                        "checksum_sha256": item.checksum_sha256,
                    }
                    for item in schemas
                ],
                indent=2,
            )
        )
        return
    try:
        from rich.console import Console
        from rich.table import Table

        table = Table(title="fetchkit portable contracts")
        table.add_column("Contract")
        table.add_column("Category")
        table.add_column("Role")
        table.add_column("Title")
        for item in schemas:
            table.add_row(item.key, item.category, item.role, item.title)
        Console().print(table)
    except ImportError:  # pragma: no cover - Rich is a core dependency
        for item in schemas:
            click.echo(f"{item.key}\t{item.category}\t{item.role}\t{item.title}")


@contracts.command(name="export")
@click.argument("destination", type=click.Path(path_type=Path))
@click.option(
    "--split",
    is_flag=True,
    help="Write manifest.json plus one JSON Schema file per contract.",
)
@click.option(
    "--load-provider-plugins",
    is_flag=True,
    help="Include installed fetchkit acquisition-provider entry points.",
)
def contracts_export(
    destination: Path,
    split: bool,
    load_provider_plugins: bool,
) -> None:
    """Export a deterministic schema, provider, and template catalog."""
    from pyfetcher.protocol import export_protocol_catalog

    try:
        catalog = _protocol_catalog(load_provider_plugins=load_provider_plugins)
        paths = export_protocol_catalog(catalog, destination, split=split)
    except (OSError, TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.secho(f"Exported {len(catalog.schemas)} contracts to {paths[0]}", fg="green")


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
