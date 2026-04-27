import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import httpx
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()

_CACHE_DIR = Path(__file__).parent.parent / "cache" / "analyst"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_BASE = "https://financialmodelingprep.com/stable"


def _cache_path(symbol: str) -> Path:
    return _CACHE_DIR / f"{symbol.upper()}.json"


def _load_cache(symbol: str) -> dict | None:
    path = _cache_path(symbol)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data["cached_at"])
        ttl_hours = float(os.getenv("FMP_CACHE_TTL_HOURS", "12"))
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours > ttl_hours:
            logger.info("analyst cache expired  symbol=%s  age_hours=%.1f", symbol, age_hours)
            return None
        logger.info("analyst cache hit  symbol=%s  age_hours=%.1f", symbol, age_hours)
        return data
    except Exception as exc:
        logger.warning("analyst cache read error  symbol=%s  error=%s", symbol, exc)
        return None


def _save_cache(symbol: str, payload: dict) -> None:
    path = _cache_path(symbol)
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("analyst cache saved  symbol=%s  path=%s", symbol, path.name)
    except Exception as exc:
        logger.warning("analyst cache write error  symbol=%s  error=%s", symbol, exc)


async def _get(client: httpx.AsyncClient, endpoint: str, params: dict) -> list | dict:
    url = f"{_BASE}/{endpoint}"
    t0 = perf_counter()
    try:
        resp = await client.get(url, params=params, timeout=15.0)
        ms = round((perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            logger.warning("FMP %s  status=%d  body=%s — skipping",
                           endpoint, resp.status_code, resp.text[:200])
            return []
        data = resp.json()
        rows = len(data) if isinstance(data, list) else 1
        logger.info("FMP %s  rows=%d  [%dms]", endpoint, rows, ms)
        return data
    except Exception as exc:
        logger.warning("FMP %s  error=%s — skipping", endpoint, exc)
        return []


def _first(data) -> dict:
    """Return first element if list, else the dict itself, else {}."""
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


@router.get("/api/analyst/{symbol}")
async def get_analyst(symbol: str):
    symbol = symbol.upper()

    cached = _load_cache(symbol)
    if cached:
        return cached

    logger.info("analyst cache miss  symbol=%s — fetching from FMP", symbol)
    t0 = perf_counter()

    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="FMP_API_KEY not set in .env")

    p = {"symbol": symbol, "apikey": api_key}

    async with httpx.AsyncClient() as client:
        estimates, pt_consensus, pt_summary, rating, grades = await asyncio.gather(
            _get(client, "analyst-estimates",    {**p, "period": "annual", "limit": 6}),
            _get(client, "price-target-consensus", p),
            _get(client, "price-target-summary",   p),
            _get(client, "ratings-snapshot",       p),
            _get(client, "grades",               {**p, "limit": 12}),
        )

    payload = {
        "symbol":              symbol,
        "cached_at":           datetime.now(timezone.utc).isoformat(),
        "estimates":           estimates if isinstance(estimates, list) else [],
        "price_target_consensus": _first(pt_consensus),
        "price_target_summary":   _first(pt_summary),
        "rating_snapshot":        _first(rating),
        "grades":              grades if isinstance(grades, list) else [],
    }

    _save_cache(symbol, payload)

    total_ms = round((perf_counter() - t0) * 1000)
    logger.info(
        "analyst done  symbol=%s  estimates=%d  grades=%d  pt_consensus=%s  [%dms]",
        symbol, len(payload["estimates"]), len(payload["grades"]),
        payload["price_target_consensus"].get("targetConsensus"), total_ms,
    )
    return payload
