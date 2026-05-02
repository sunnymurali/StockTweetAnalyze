import asyncio
import logging

import yfinance as yf
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)


def _fetch_yf_news(symbol: str, limit: int = 10) -> list[dict]:
    try:
        raw = yf.Ticker(symbol).news or []
        articles = []
        for item in raw[:limit]:
            content = item.get("content", {})
            articles.append({
                "title":     content.get("title", item.get("title", "")),
                "publisher": content.get("provider", {}).get("displayName", ""),
                "link":      content.get("canonicalUrl", {}).get("url", item.get("link", "")),
                "published": content.get("pubDate", ""),
                "summary":   content.get("summary", ""),
            })
        return articles
    except Exception as e:
        logger.error("yfinance news error for %s: %s", symbol, e)
        return []


@router.get("/api/news/{symbol}")
async def get_news(symbol: str):
    articles = await asyncio.to_thread(_fetch_yf_news, symbol.upper())
    return {"news": articles}
