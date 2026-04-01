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

import click


@click.group()
@click.version_option(package_name="pyfetcher")
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


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
