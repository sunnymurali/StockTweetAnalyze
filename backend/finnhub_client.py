"""
Shared Finnhub API client — thin HTTP wrapper used by routers.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests
from fastapi import HTTPException

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"
ET = ZoneInfo("America/New_York")


def _key() -> str:
    k = os.getenv("FINNHUB_API_KEY", "").strip()
    if not k:
        raise HTTPException(status_code=500, detail="FINNHUB_API_KEY not configured")
    return k


def fh_get(path: str, params: dict) -> dict | list:
    params["token"] = _key()
    try:
        resp = requests.get(f"{FINNHUB_BASE}{path}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Finnhub request failed %s: %s", path, e)
        raise HTTPException(status_code=502, detail=f"Finnhub error: {e}")


# ── Quote ──────────────────────────────────────────────────────────────

def fetch_quote(symbol: str) -> dict:
    sym = symbol.upper()
    try:
        q = fh_get("/quote", {"symbol": sym})
        p = fh_get("/stock/profile2", {"symbol": sym})

        price = q.get("c")
        if not price:
            return {"symbol": sym, "error": "No price data available"}

        mkt_cap = p.get("marketCapitalization")
        if mkt_cap:
            mkt_cap = mkt_cap * 1_000_000  # Finnhub returns in millions

        return {
            "symbol":     sym,
            "name":       p.get("name"),
            "sector":     p.get("finnhubIndustry"),
            "price":      round(float(price), 2),
            "change":     round(float(q["d"]), 2)  if q.get("d")  else None,
            "change_pct": round(float(q["dp"]), 2) if q.get("dp") else None,
            "day_high":   round(float(q["h"]), 2)  if q.get("h")  else None,
            "day_low":    round(float(q["l"]), 2)  if q.get("l")  else None,
            "volume":     None,  # not in Finnhub quote endpoint
            "market_cap": mkt_cap,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Finnhub quote error for %s: %s", sym, e)
        return {"symbol": sym, "error": str(e)}


# ── Candles / Charts ───────────────────────────────────────────────────

def _now_unix() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _unix_days_ago(n: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=n)).timestamp())


def fetch_candles(symbol: str, timespan: str) -> list[dict]:
    """
    timespan=day  → 5-min bars, last ~24h filtered to most recent trading day
    timespan=week → 60-min bars, last 7 days
    timespan=3y   → weekly bars, last 3 years
    Returns list of {time, open, high, low, close, volume} dicts.
    """
    sym = symbol.upper()
    now = _now_unix()

    if timespan == "day":
        resolution, from_ts = "5", _unix_days_ago(1)
    elif timespan == "week":
        resolution, from_ts = "60", _unix_days_ago(7)
    else:  # 3y
        resolution, from_ts = "W", _unix_days_ago(3 * 365)

    data = fh_get("/stock/candle", {
        "symbol": sym, "resolution": resolution,
        "from": from_ts, "to": now,
    })

    if data.get("s") != "ok":
        return []

    timestamps = data["t"]
    bars = [
        {
            "time":   timestamps[i],
            "open":   round(data["o"][i], 4),
            "high":   round(data["h"][i], 4),
            "low":    round(data["l"][i], 4),
            "close":  round(data["c"][i], 4),
            "volume": int(data["v"][i]) if data.get("v") else 0,
        }
        for i in range(len(timestamps))
    ]

    # For 1D: keep only bars from the most recent date in the result
    if timespan == "day" and bars:
        latest_date = datetime.fromtimestamp(bars[-1]["time"], tz=timezone.utc).date()
        bars = [b for b in bars if datetime.fromtimestamp(b["time"], tz=timezone.utc).date() == latest_date]

    return bars


# ── News ───────────────────────────────────────────────────────────────

def fetch_news(symbol: str, days_back: int = 7, limit: int = 10) -> list[dict]:
    sym = symbol.upper()
    to_dt   = datetime.now(timezone.utc)
    from_dt = to_dt - timedelta(days=days_back)

    articles = fh_get("/company-news", {
        "symbol": sym,
        "from":   from_dt.strftime("%Y-%m-%d"),
        "to":     to_dt.strftime("%Y-%m-%d"),
    })

    if not isinstance(articles, list):
        return []

    result = []
    for a in articles:
        if len(result) >= limit:
            break
        ts = a.get("datetime")
        published = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            if ts else None
        )
        result.append({
            "title":     a.get("headline", ""),
            "publisher": a.get("source", ""),
            "published": published,
            "link":      a.get("url", ""),
            "summary":   a.get("summary", ""),
        })

    return result


# ── Basic Financials (metrics) ─────────────────────────────────────────

def fetch_metrics(symbol: str) -> dict:
    sym = symbol.upper()
    data = fh_get("/stock/metric", {"symbol": sym, "metric": "all"})
    return data.get("metric", {}), data.get("series", {})
