import logging
from fastapi import APIRouter, HTTPException
from finnhub_client import fetch_candles

router = APIRouter()
logger = logging.getLogger(__name__)


def _yfinance_fallback(symbol: str, timespan: str) -> list[dict]:
    import yfinance as yf
    period_map = {"day": ("1d", "5m"), "week": ("5d", "1h"), "3y": ("3y", "1wk")}
    period, interval = period_map.get(timespan, ("3y", "1wk"))
    hist = yf.Ticker(symbol).history(period=period, interval=interval)
    if hist.empty:
        return []
    return [
        {
            "time":   int(ts.timestamp()),
            "open":   round(float(row["Open"]),  4),
            "high":   round(float(row["High"]),  4),
            "low":    round(float(row["Low"]),   4),
            "close":  round(float(row["Close"]), 4),
            "volume": int(row["Volume"]),
        }
        for ts, row in hist.iterrows()
    ]


@router.get("/api/chart/{symbol}")
def get_chart(symbol: str, timespan: str = "day"):
    symbol = symbol.upper()
    try:
        bars = fetch_candles(symbol, timespan)
        if not bars:
            logger.info("Finnhub returned no bars for %s %s — falling back to yfinance", symbol, timespan)
            bars = _yfinance_fallback(symbol, timespan)
    except Exception as e:
        logger.warning("Finnhub chart error for %s (%s): %s — trying yfinance", symbol, timespan, e)
        try:
            bars = _yfinance_fallback(symbol, timespan)
        except Exception as e2:
            raise HTTPException(status_code=502, detail=f"Chart data unavailable: {e2}")

    return {"symbol": symbol, "timespan": timespan, "bars": bars, "count": len(bars)}
