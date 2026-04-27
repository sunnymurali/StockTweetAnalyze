"""
MCP Server — live stock quotes via yfinance (no API key needed).
"""

import asyncio
import json
from typing import Any

import yfinance as yf
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("quote-mcp")


def fetch_quote(symbol: str) -> dict:
    ticker = yf.Ticker(symbol)
    fi = ticker.fast_info
    try:
        price = round(fi.last_price, 2)
        prev_close = round(fi.previous_close, 2)
        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0
        return {
            "symbol": symbol.upper(),
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "volume": fi.three_month_average_volume,
            "market_cap": fi.market_cap,
            "day_high": round(fi.day_high, 2) if fi.day_high else None,
            "day_low": round(fi.day_low, 2) if fi.day_low else None,
        }
    except Exception as e:
        return {"symbol": symbol.upper(), "error": str(e)}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_quote",
            description="Get live stock quote for a ticker symbol",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Ticker e.g. AAPL"}
                },
                "required": ["symbol"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "get_quote":
        symbol = arguments["symbol"].upper()
        quote = fetch_quote(symbol)
        return [TextContent(type="text", text=json.dumps(quote))]
    return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
