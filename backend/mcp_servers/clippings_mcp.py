"""
MCP Server — reads Obsidian clippings from WebObsidian and serves tweets.
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

CLIPPINGS_DIR = Path(os.getenv(
    "CLIPPINGS_DIR",
    r"C:\Users\Sunny\Downloads\InvestmentWiki\Clippings"
))

server = Server("clippings-mcp")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from body."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm, body = parts[1], parts[2].strip()
    meta = {}
    for line in fm.strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return meta, body


NON_TICKERS = {
    # Exchanges & regulators
    "NYSE", "NASDAQ", "AMEX", "OTC", "CME", "CBOE", "SEC", "CFTC", "FINRA",
    # Macro & indices
    "FED", "FOMC", "IMF", "ECB", "GDP", "CPI", "PPI", "PCE", "PMI", "ISM", "VIX",
    # Financial metrics
    "EPS", "PE", "PEG", "ROE", "ROA", "DCF", "FCF", "EBITDA", "GAAP", "EBIT",
    # Vehicle types
    "ETF", "IPO", "SPO", "SPAC", "REIT",
    # Options
    "ATM", "ITM", "OTM", "IV", "DTE", "PUT", "PUTS", "CALL", "CALLS",
    # Trading actions & sentiment
    "BUY", "SELL", "HOLD", "LONG", "SHORT", "COVER", "HEDGE",
    "BULL", "BEAR", "FLAT", "BEAT", "MISS",
    # Price / market movement
    "HIGH", "LOW", "OPEN", "CLOSE", "MOVE", "JUMP", "DROP", "RISE", "FALL",
    # Time
    "AM", "PM", "EST", "PST", "CST", "UTC", "EOD", "EOM",
    "Q1", "Q2", "Q3", "Q4", "YTD", "QTD", "YOY", "QOQ",
    "WEEK", "MONTH", "YEAR", "NEXT", "LAST", "TODAY",
    "FY", "FQ", "QTR",
    # Currencies & geo
    "USD", "EUR", "GBP", "JPY", "CAD", "AUD",
    "USA", "US", "UK", "EU",
    # Corporate roles
    "CEO", "CFO", "COO", "CTO", "CPO",
    # Common all-caps words in finance tweets
    "AI", "IT", "OR", "AND", "FOR", "NOT", "ALL", "NEW", "TOP", "NOW",
    "THE", "BIG", "WITH", "THIS", "THAT", "THAN", "ALSO", "JUST",
    "RATE", "RATES", "FUND", "BOND", "BONDS", "BANK", "CASH",
    "DEAL", "NEWS", "NOTE", "RISK", "GAIN", "LOSS", "FLOW",
    "STRONG", "WEAK", "ABOVE", "BELOW", "NEAR",
    # Short common words often written in caps
    "TO", "IN", "OF", "AT", "BY", "ON", "IF", "NO", "SO", "UP", "GO",
    "HAS", "WAS", "ARE", "HAD", "DID", "CAN", "MAY", "WILL",
    "GET", "GOT", "SET", "HIT", "RUN", "DUE", "OFF", "OUT", "PER",
    "VS", "VIA", "RE",
}


def extract_tickers(text: str) -> list[str]:
    # Pattern 1: $TICKER cashtags — most reliable
    dollar = re.findall(r'\$([A-Z]{1,5})', text)

    # Pattern 2: (TICKER) parentheses
    raw_parens = re.findall(r'\(([A-Z]{1,5})\)', text)
    parens = [t for t in raw_parens if t.isalpha() and t not in NON_TICKERS]

    # Pattern 3: bare ALL-CAPS words at word boundaries (no $ prefix)
    # \b ensures we don't match mid-word; negative lookbehind skips $TICKER already caught
    bare_raw = re.findall(r'(?<!\$)\b([A-Z]{2,5})\b', text)
    bare = [t for t in bare_raw if t.isalpha() and t not in NON_TICKERS]

    return sorted(set(dollar + parens + bare))


def _parse_tweet_file(f: Path) -> dict | None:
    """Parse any supported tweet file format into a unified dict."""
    try:
        raw = f.read_text(encoding="utf-8")
    except Exception:
        return None

    meta, body = parse_frontmatter(raw)

    # ── Format A: tweet_SNOWFLAKEID.md ──────────────────────────────
    if f.stem.startswith("tweet_"):
        tweet_id = f.stem.removeprefix("tweet_")
        tickers_raw = meta.get("tickers", "[]")
        tickers = re.findall(r'[A-Z]{2,5}', tickers_raw)
        if not tickers:
            tickers = extract_tickers(body)
        author = meta.get("author", "@OptionsHawk")
        return {
            "id":     tweet_id,
            "text":   body,
            "author": author,
            "date":   meta.get("date", ""),
            "source": meta.get("source", ""),
            "tickers": tickers,
            "_sort_key": int(tweet_id) if tweet_id.isdigit() else 0,
        }

    # ── Format B: "Post by @Author on X N.md" (WebClipper format) ────
    source = meta.get("source", "")
    # Extract tweet ID from source URL  e.g. https://x.com/OptionsHawk/status/2047130279404519801
    id_match = re.search(r'/status/(\d+)', source)
    tweet_id = id_match.group(1) if id_match else re.sub(r'[^0-9]', '', f.stem) or f.stem

    # Author: strip Obsidian wikilink [[...]] if present
    raw_author = meta.get("author", "")
    if isinstance(raw_author, list):
        raw_author = raw_author[0] if raw_author else ""
    author = re.sub(r'[\[\]@]', '', str(raw_author)).strip()
    if author and not author.startswith("@"):
        author = "@" + author

    tickers = extract_tickers(body)

    date = meta.get("published") or meta.get("date") or meta.get("created", "")

    return {
        "id":     tweet_id,
        "text":   body,
        "author": author or "@OptionsHawk",
        "date":   str(date),
        "source": source,
        "tickers": tickers,
        "_sort_key": int(tweet_id) if tweet_id.isdigit() else 0,
    }


def load_tweets(limit: int = 50) -> list[dict]:
    files = list(CLIPPINGS_DIR.glob("tweet_*.md")) + list(CLIPPINGS_DIR.glob("Post by *.md"))

    parsed = [r for f in files if (r := _parse_tweet_file(f)) is not None]
    parsed.sort(key=lambda r: r["_sort_key"], reverse=True)

    tweets = []
    for r in parsed[:limit]:
        r.pop("_sort_key", None)
        tweets.append(r)
    return tweets


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_tweets",
            description="List recent tweets from Obsidian clippings",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 50}
                }
            }
        ),
        Tool(
            name="get_tweet",
            description="Get a single tweet by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "tweet_id": {"type": "string"}
                },
                "required": ["tweet_id"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "list_tweets":
        limit = arguments.get("limit", 50)
        tweets = load_tweets(limit)
        return [TextContent(type="text", text=json.dumps({"tweets": tweets}))]

    if name == "get_tweet":
        tweet_id = arguments["tweet_id"]
        path = CLIPPINGS_DIR / f"tweet_{tweet_id}.md"
        if not path.exists():
            return [TextContent(type="text", text=json.dumps({"error": "not found"}))]
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        tickers = re.findall(r'[A-Z]{1,5}', meta.get("tickers", "[]"))
        tweet = {
            "id": tweet_id,
            "text": body,
            "author": meta.get("author", ""),
            "date": meta.get("date", ""),
            "source": meta.get("source", ""),
            "tickers": tickers,
        }
        return [TextContent(type="text", text=json.dumps(tweet))]

    return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
