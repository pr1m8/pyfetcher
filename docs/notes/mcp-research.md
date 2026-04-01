# MCP Server Research Notes

## Architecture Decision

pyfetcher exposes its capabilities as an MCP server via FastMCP. LangChain agents
can consume it via langchain-mcp-adapters. The core library stays unchanged --
the MCP layer is a thin wrapper.

```
pyfetcher (core library)
    |
    v
pyfetcher.mcp (FastMCP server)        <-- NEW
    |                    |
    v                    v
stdio/HTTP           langchain-mcp-adapters
(Claude Desktop,     (LangChain/LangGraph agents)
 Claude Code, etc.)
```

## FastMCP Key Patterns

### Server Setup

```python
from fastmcp import FastMCP

mcp = FastMCP("pyfetcher", version="0.2.0")

@mcp.tool()
async def fetch_url(url: str, timeout: int = 30) -> dict:
    """Fetch a URL."""
    ...

@mcp.resource("pyfetcher://profiles")
def list_browser_profiles() -> str:
    """List available browser profiles."""
    ...

@mcp.prompt()
def research_prompt(topic: str) -> str:
    """Generate a web research prompt."""
    ...

if __name__ == "__main__":
    mcp.run()  # stdio default, or transport="http"
```

### Key APIs

- `@mcp.tool()` -- Decorator, auto-generates JSON Schema from type hints
- `@mcp.resource("uri://path/{param}")` -- Static or template resources
- `@mcp.prompt()` -- Prompt templates with arguments
- `Context = CurrentContext()` -- Logging, progress, state within tools
- `ToolError` -- User-friendly error messages to LLMs
- `mcp.run(transport="http", port=8000)` -- HTTP transport for remote access

### Structured Output

FastMCP auto-wraps return values:

- Pydantic models -> structured JSON content
- Dicts -> structured JSON content
- Primitives -> `{"result": value}`

### Error Handling

```python
from fastmcp import ToolError

@mcp.tool()
async def fetch(url: str) -> dict:
    try:
        response = await pyfetcher.afetch(url)
        return {...}
    except Exception as e:
        raise ToolError(f"Fetch failed: {e}")
```

### Running

```bash
# stdio (Claude Desktop / Claude Code)
python -m pyfetcher.mcp.server

# HTTP (remote clients, LangChain)
fastmcp run src/pyfetcher/mcp/server.py --transport http --port 8000

# Or via Makefile
make mcp          # stdio
make mcp-http     # http on port 8000
```

## LangChain Integration

### langchain-mcp-adapters

Bridges MCP servers to LangChain tools automatically:

```python
from langchain_mcp_adapters import MultiServerMCPClient

client = MultiServerMCPClient({
    "pyfetcher": {
        "transport": "http",
        "url": "http://localhost:8000/mcp"
    }
})

tools = await client.get_tools()  # -> list[BaseTool]
```

### Creating Agents

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

agent = create_react_agent(ChatOpenAI(), tools)
result = await agent.ainvoke({"messages": [("user", "Fetch https://example.com")]})
```

## Planned MCP Tools

| Tool                | Description                      | Input                          | Output                           |
| ------------------- | -------------------------------- | ------------------------------ | -------------------------------- |
| `fetch_url`         | Fetch a URL with browser headers | url, backend, profile, timeout | status, headers, text, elapsed   |
| `fetch_multiple`    | Batch fetch URLs concurrently    | urls[], concurrency            | results[]                        |
| `scrape_css`        | Extract content via CSS selector | url, selector                  | elements[]                       |
| `scrape_links`      | Extract links from a page        | url, same_domain_only          | links[]                          |
| `scrape_text`       | Extract readable text            | url, selector?                 | text                             |
| `scrape_metadata`   | Extract page metadata            | url                            | title, description, og, favicons |
| `scrape_forms`      | Extract form data                | url                            | forms[] with fields              |
| `scrape_table`      | Extract table data               | url, selector                  | rows[][]                         |
| `check_robots`      | Check robots.txt                 | url, path, user_agent          | allowed, rules                   |
| `parse_sitemap`     | Parse XML sitemap                | url                            | entries[]                        |
| `generate_headers`  | Preview browser headers          | profile                        | headers dict                     |
| `list_profiles`     | List available profiles          | -                              | profile names + details          |
| `random_user_agent` | Generate random UA               | browser?, platform?, mobile?   | ua string                        |
| `extract_article`   | Extract article text             | url or html                    | text, title, author              |
| `convert_html`      | HTML -> markdown/plaintext       | html, format                   | converted text                   |
| `download_file`     | Download to local path           | url, destination               | path, size, checksum             |

## Planned MCP Resources

| Resource URI                  | Description                               |
| ----------------------------- | ----------------------------------------- |
| `pyfetcher://profiles`        | List of all browser profiles with details |
| `pyfetcher://profiles/{name}` | Headers for a specific profile            |
| `pyfetcher://backends`        | Backend capabilities table                |
| `pyfetcher://version`         | Version and feature info                  |

## Planned MCP Prompts

| Prompt          | Args       | Description                                         |
| --------------- | ---------- | --------------------------------------------------- |
| `web_research`  | topic      | Research a topic by fetching and extracting content |
| `site_audit`    | url        | Audit a website (meta, links, robots, sitemap)      |
| `scrape_guide`  | url, goal  | Guide for scraping a specific site                  |
| `compare_pages` | url1, url2 | Compare content of two pages                        |

## Structured Output Models

```python
class FetchResult(BaseModel):
    url: str
    final_url: str
    status_code: int
    ok: bool
    content_type: str | None
    headers: dict[str, str]
    text: str | None
    elapsed_ms: float

class ScrapeResult(BaseModel):
    url: str
    selector: str
    elements: list[str]
    count: int

class LinkResult(BaseModel):
    url: str
    text: str
    is_external: bool

class MetadataResult(BaseModel):
    title: str | None
    description: str | None
    canonical_url: str | None
    og_title: str | None
    og_image: str | None
    favicons: list[str]

class ArticleResult(BaseModel):
    text: str | None
    title: str | None
    authors: list[str]
    publish_date: str | None

class DownloadResult(BaseModel):
    path: str
    size_bytes: int
    checksum_sha256: str
    mime_type: str | None
```

## Package Structure

```
src/pyfetcher/mcp/
├── __init__.py
├── server.py        # FastMCP server with all tools/resources/prompts
├── models.py        # Pydantic output models (FetchResult, ScrapeResult, etc.)
└── __main__.py      # python -m pyfetcher.mcp entry point
```

## Dependencies

```toml
[project.optional-dependencies]
mcp = ["fastmcp>=2.0", "langchain-mcp-adapters>=0.1"]
```

## Makefile Targets

```makefile
mcp:          ## Run MCP server (stdio)
mcp-http:     ## Run MCP server (HTTP on port 8000)
mcp-list:     ## List available MCP tools/resources
```
