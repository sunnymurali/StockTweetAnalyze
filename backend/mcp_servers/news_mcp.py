"""
MCP Server — latest stock news via yfinance (no API key needed).
"""

import asyncio
import json
from datetime import datetime
from typing import Any

import yfinance as yf
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("news-mcp")


def fetch_news(symbol: str, limit: int = 5) -> list[dict]:
    ticker = yf.Ticker(symbol)
    raw = ticker.news or []
    articles = []
    for item in raw[:limit]:
        content = item.get("content", {})
        pub_ts = content.get("pubDate", "")
        articles.append({
            "title": content.get("title", item.get("title", "")),
            "publisher": content.get("provider", {}).get("displayName", ""),
            "link": content.get("canonicalUrl", {}).get("url", item.get("link", "")),
            "published": pub_ts,
            "summary": content.get("summary", ""),
        })
    return articles


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_news",
            description="Get latest news articles for a stock ticker",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["symbol"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "get_news":
        symbol = arguments["symbol"].upper()
        limit = arguments.get("limit", 5)
        articles = fetch_news(symbol, limit)
        return [TextContent(type="text", text=json.dumps({"symbol": symbol, "news": articles}))]
    return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
