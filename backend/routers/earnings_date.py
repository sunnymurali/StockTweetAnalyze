import asyncio
import logging

import yfinance as yf
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)


def _fetch(symbol: str) -> dict:
    try:
        cal = yf.Ticker(symbol).calendar
        if not cal:
            return {}

        dates = cal.get("Earnings Date", [])
        next_date = str(dates[0]) if dates else None

        def _f(v):
            try:
                return round(float(v), 4) if v is not None else None
            except (TypeError, ValueError):
                return None

        return {
            "earnings_date":     next_date,
            "eps_avg":           _f(cal.get("Earnings Average")),
            "eps_low":           _f(cal.get("Earnings Low")),
            "eps_high":          _f(cal.get("Earnings High")),
            "revenue_avg":       _f(cal.get("Revenue Average")),
            "revenue_low":       _f(cal.get("Revenue Low")),
            "revenue_high":      _f(cal.get("Revenue High")),
        }
    except Exception as e:
        logger.error("earnings_date error for %s: %s", symbol, e)
        return {}


@router.get("/api/earnings-date/{symbol}")
async def get_earnings_date(symbol: str):
    return await asyncio.to_thread(_fetch, symbol.upper())
