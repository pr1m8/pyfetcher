"""MCP server for :mod:`pyfetcher`.

Purpose:
    Expose pyfetcher's fetching, scraping, header generation, and content
    extraction capabilities as MCP tools, resources, and prompts via FastMCP.
    Compatible with Claude Desktop, Claude Code, and LangChain agents via
    langchain-mcp-adapters.
"""

from __future__ import annotations
