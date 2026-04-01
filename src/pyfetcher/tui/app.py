"""TUI application for pyfetcher.

Purpose:
    Provide an interactive terminal user interface using ``textual`` for
    building HTTP requests, previewing generated headers, fetching URLs,
    inspecting responses, and scraping content.

Design:
    - Built on ``textual`` for a rich terminal experience with widgets.
    - Supports URL input, method selection, header preview, and response
      display in a split-pane layout.
    - Scraping operations (CSS extraction, link harvesting, text extraction)
      are accessible via keyboard shortcuts.
    - The TUI integrates the full pyfetcher stack including header generation,
      rate limiting, and retry logic.

Examples:
    ::

        $ pyfetcher-tui
        $ python -m pyfetcher.tui.app
"""

from __future__ import annotations

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import (
        Button,
        Footer,
        Header,
        Input,
        RichLog,
        Select,
        Static,
        TextArea,
    )

    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


def _check_textual() -> None:
    """Raise a helpful error if textual is not installed."""
    if not HAS_TEXTUAL:
        raise ImportError(
            "The pyfetcher TUI requires 'textual'. " "Install it with: pip install 'pyfetcher[tui]'"
        )


if HAS_TEXTUAL:

    class PyfetcherApp(App[None]):
        """Interactive TUI for pyfetcher.

        Provides a terminal interface for building and executing HTTP requests,
        previewing browser headers, and scraping content. Uses a split-pane
        layout with request configuration on the left and response display
        on the right.

        Keybindings:
            - ``ctrl+f``: Execute the current request.
            - ``ctrl+h``: Preview generated headers.
            - ``ctrl+l``: Extract links from last response.
            - ``ctrl+t``: Extract readable text from last response.
            - ``q``: Quit the application.
        """

        TITLE = "pyfetcher"
        CSS = """
        #main-container {
            layout: horizontal;
        }
        #left-panel {
            width: 1fr;
            height: 100%;
            border-right: solid $primary;
            padding: 1;
        }
        #right-panel {
            width: 2fr;
            height: 100%;
            padding: 1;
        }
        #url-input {
            margin-bottom: 1;
        }
        #method-select {
            width: 20;
            margin-bottom: 1;
        }
        #profile-select {
            width: 30;
            margin-bottom: 1;
        }
        #response-log {
            height: 100%;
        }
        .button-row {
            height: 3;
            margin-bottom: 1;
        }
        """

        BINDINGS = [
            Binding("ctrl+f", "do_fetch", "Fetch", show=True),
            Binding("ctrl+h", "preview_headers", "Headers", show=True),
            Binding("ctrl+l", "extract_links", "Links", show=True),
            Binding("ctrl+t", "extract_text", "Text", show=True),
            Binding("q", "quit", "Quit", show=True),
        ]

        def __init__(self) -> None:
            super().__init__()
            self._last_html: str = ""
            self._last_url: str = ""

        def compose(self) -> ComposeResult:
            """Compose the TUI layout."""
            yield Header()
            with Horizontal(id="main-container"):
                with Vertical(id="left-panel"):
                    yield Static("URL:", classes="label")
                    yield Input(
                        placeholder="https://example.com",
                        id="url-input",
                    )
                    yield Static("Method:", classes="label")
                    yield Select(
                        [
                            (m, m)
                            for m in ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"]
                        ],
                        value="GET",
                        id="method-select",
                    )
                    yield Static("Profile:", classes="label")
                    yield Select(
                        self._get_profile_options(),
                        value="chrome_win",
                        id="profile-select",
                    )
                    with Horizontal(classes="button-row"):
                        yield Button("Fetch", variant="primary", id="fetch-btn")
                        yield Button("Headers", variant="default", id="headers-btn")
                    with Horizontal(classes="button-row"):
                        yield Button("Links", variant="default", id="links-btn")
                        yield Button("Text", variant="default", id="text-btn")
                        yield Button("Meta", variant="default", id="meta-btn")
                    yield Static("Custom Headers:", classes="label")
                    yield TextArea(id="custom-headers", language="toml")
                with Vertical(id="right-panel"):
                    yield RichLog(id="response-log", highlight=True, markup=True)
            yield Footer()

        def _get_profile_options(self) -> list[tuple[str, str]]:
            """Get browser profile options for the select widget."""
            from pyfetcher.headers.profiles import list_profiles

            profiles = list_profiles()
            return [(p, p) for p in profiles]

        def _get_url(self) -> str:
            """Get the current URL from the input."""
            url_input = self.query_one("#url-input", Input)
            return url_input.value.strip()

        def _get_method(self) -> str:
            """Get the current HTTP method."""
            method_select = self.query_one("#method-select", Select)
            return str(method_select.value)

        def _get_profile(self) -> str:
            """Get the current browser profile."""
            profile_select = self.query_one("#profile-select", Select)
            return str(profile_select.value)

        def _get_log(self) -> RichLog:
            """Get the response log widget."""
            return self.query_one("#response-log", RichLog)

        def on_button_pressed(self, event: Button.Pressed) -> None:
            """Handle button presses."""
            button_id = event.button.id
            if button_id == "fetch-btn":
                self.action_do_fetch()
            elif button_id == "headers-btn":
                self.action_preview_headers()
            elif button_id == "links-btn":
                self.action_extract_links()
            elif button_id == "text-btn":
                self.action_extract_text()
            elif button_id == "meta-btn":
                self.action_extract_meta()

        def action_do_fetch(self) -> None:
            """Execute the current request."""
            url = self._get_url()
            if not url:
                self._get_log().write("[red]Please enter a URL[/red]")
                return

            log = self._get_log()
            log.write(f"[cyan]Fetching {url}...[/cyan]")

            try:
                from pyfetcher.contracts.request import FetchRequest
                from pyfetcher.fetch.service import FetchService
                from pyfetcher.headers.browser import BrowserHeaderProvider

                service = FetchService(header_provider=BrowserHeaderProvider(self._get_profile()))
                response = service.fetch(
                    FetchRequest(url=url, method=self._get_method())  # type: ignore[arg-type]
                )
                service.close()

                self._last_html = response.text or ""
                self._last_url = url

                log.write(f"[green]Status: {response.status_code}[/green]")
                log.write(f"URL: {response.final_url}")
                log.write(f"Elapsed: {response.elapsed_ms:.1f}ms")
                log.write(f"Content-Type: {response.content_type or 'N/A'}")
                log.write(f"Body length: {len(response.text or '')} chars")
                log.write("---")

            except Exception as exc:
                log.write(f"[red]Error: {exc}[/red]")

        def action_preview_headers(self) -> None:
            """Preview generated headers for the current profile."""
            from pyfetcher.headers.browser import get_best_browser_headers

            log = self._get_log()
            profile = self._get_profile()
            headers = get_best_browser_headers(profile)

            log.write(f"[cyan]Headers for profile: {profile}[/cyan]")
            for key, val in headers.items():
                log.write(f"  [green]{key}[/green]: {val}")
            log.write("---")

        def action_extract_links(self) -> None:
            """Extract links from the last fetched page."""
            if not self._last_html:
                self._get_log().write("[yellow]No page loaded. Fetch a URL first.[/yellow]")
                return

            from pyfetcher.scrape.links import extract_links

            log = self._get_log()
            links = extract_links(self._last_html, base_url=self._last_url)
            log.write(f"[cyan]Found {len(links)} links:[/cyan]")
            for link in links[:50]:
                marker = "[red][ext][/red]" if link.is_external else "[green][int][/green]"
                log.write(f"  {marker} {link.url}")
            if len(links) > 50:
                log.write(f"  ... and {len(links) - 50} more")
            log.write("---")

        def action_extract_text(self) -> None:
            """Extract readable text from the last fetched page."""
            if not self._last_html:
                self._get_log().write("[yellow]No page loaded. Fetch a URL first.[/yellow]")
                return

            from pyfetcher.scrape.content import extract_readable_text

            log = self._get_log()
            text = extract_readable_text(self._last_html)
            log.write("[cyan]Readable text:[/cyan]")
            log.write(text[:2000])
            if len(text) > 2000:
                log.write(f"... ({len(text) - 2000} more chars)")
            log.write("---")

        def action_extract_meta(self) -> None:
            """Extract metadata from the last fetched page."""
            if not self._last_html:
                self._get_log().write("[yellow]No page loaded. Fetch a URL first.[/yellow]")
                return

            from pyfetcher.metadata.html import extract_basic_html_metadata
            from pyfetcher.metadata.opengraph import extract_open_graph_metadata

            log = self._get_log()
            meta = extract_basic_html_metadata(self._last_html, base_url=self._last_url)
            og = extract_open_graph_metadata(self._last_html)

            log.write("[cyan]Page Metadata:[/cyan]")
            log.write(f"  Title: {meta.title or 'N/A'}")
            log.write(f"  Description: {meta.description or 'N/A'}")
            log.write(f"  Canonical: {meta.canonical_url or 'N/A'}")
            if og:
                log.write(f"  OG Title: {og.title or 'N/A'}")
                log.write(f"  OG Image: {og.image or 'N/A'}")
                log.write(f"  OG Type: {og.type or 'N/A'}")
            log.write("---")


def run_tui() -> None:
    """Launch the pyfetcher TUI.

    Raises:
        ImportError: If ``textual`` is not installed.
    """
    _check_textual()
    app = PyfetcherApp()
    app.run()


if __name__ == "__main__":
    run_tui()
