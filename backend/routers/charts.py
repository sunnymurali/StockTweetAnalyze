import os
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests
import yfinance as yf
from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)

AV_BASE = "https://www.alphavantage.co/query"
ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Alpha Vantage helpers
# ---------------------------------------------------------------------------

def av_fetch(params: dict) -> dict:
    try:
        resp = requests.get(AV_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Alpha Vantage request failed: {e}")

    if "Error Message" in data:
        raise HTTPException(status_code=404, detail=data["Error Message"])
    if "Note" in data or "Information" in data:
        msg = data.get("Note") or data.get("Information", "")
        raise HTTPException(status_code=429, detail=f"Alpha Vantage rate limit: {msg[:120]}")
    return data


def intraday_to_unix(ts_str: str) -> int:
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET)
    return int(dt.timestamp())


def date_to_unix(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def bars_from_av(symbol: str, timespan: str, key: str) -> list[dict]:
    if timespan == "day":
        data = av_fetch({
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": "5min",
            "outputsize": "compact",
            "apikey": key,
        })
        series = data.get("Time Series (5min)", {})
        sorted_items = sorted(series.items())
        if sorted_items:
            latest_date = sorted_items[-1][0][:10]
            sorted_items = [(k, v) for k, v in sorted_items if k.startswith(latest_date)]
        return [
            {
                "time": intraday_to_unix(ts),
                "open": float(v["1. open"]), "high": float(v["2. high"]),
                "low": float(v["3. low"]), "close": float(v["4. close"]),
                "volume": int(float(v["5. volume"])),
            }
            for ts, v in sorted_items
        ]

    elif timespan == "week":
        data = av_fetch({
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": "60min",
            "outputsize": "compact",
            "apikey": key,
        })
        series = data.get("Time Series (60min)", {})
        sorted_items = sorted(series.items())
        if sorted_items:
            cutoff = (datetime.now(ET) - timedelta(days=7)).strftime("%Y-%m-%d")
            sorted_items = [(k, v) for k, v in sorted_items if k[:10] >= cutoff]
        return [
            {
                "time": intraday_to_unix(ts),
                "open": float(v["1. open"]), "high": float(v["2. high"]),
                "low": float(v["3. low"]), "close": float(v["4. close"]),
                "volume": int(float(v["5. volume"])),
            }
            for ts, v in sorted_items
        ]

    else:  # 3y
        data = av_fetch({
            "function": "TIME_SERIES_WEEKLY",
            "symbol": symbol,
            "apikey": key,
        })
        series = data.get("Weekly Time Series", {})
        cutoff = (datetime.now(timezone.utc) - timedelta(days=3 * 365)).strftime("%Y-%m-%d")
        sorted_items = sorted((k, v) for k, v in series.items() if k >= cutoff)
        return [
            {
                "time": date_to_unix(ts),
                "open": float(v["1. open"]), "high": float(v["2. high"]),
                "low": float(v["3. low"]), "close": float(v["4. close"]),
                "volume": int(float(v["5. volume"])),
            }
            for ts, v in sorted_items
        ]


# ---------------------------------------------------------------------------
# yfinance fallback
# ---------------------------------------------------------------------------

def bars_from_yfinance(symbol: str, timespan: str) -> list[dict]:
    period_map = {"day": ("1d", "5m"), "week": ("5d", "1h"), "3y": ("3y", "1wk")}
    period, interval = period_map.get(timespan, ("3y", "1wk"))
    hist = yf.Ticker(symbol).history(period=period, interval=interval)
    if hist.empty:
        return []
    return [
        {
            "time": int(ts.timestamp()),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row["Volume"]),
        }
        for ts, row in hist.iterrows()
    ]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/api/chart/{symbol}")
def get_chart(symbol: str, timespan: str = "day"):
    """
    timespan=day  → 5-min bars, current trading day
    timespan=week → 60-min bars, last 7 calendar days
    timespan=3y   → weekly bars, last 3 years
    Uses Alpha Vantage when ALPHA_VANTAGE_API_KEY is set, otherwise yfinance.
    """
    symbol = symbol.upper()
    key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()

    try:
        if key:
            bars = bars_from_av(symbol, timespan, key)
        else:
            logger.info("No AV key — using yfinance for %s", symbol)
            bars = bars_from_yfinance(symbol, timespan)
    except HTTPException as e:
        if e.status_code == 429:
            logger.warning("Alpha Vantage rate limit hit — falling back to yfinance for %s", symbol)
            bars = bars_from_yfinance(symbol, timespan)
        else:
            raise
    except Exception as e:
        logger.error("Chart error for %s (%s): %s", symbol, timespan, e)
        raise HTTPException(status_code=502, detail=f"Chart data error: {e}")

    return {"symbol": symbol, "timespan": timespan, "bars": bars, "count": len(bars)}
