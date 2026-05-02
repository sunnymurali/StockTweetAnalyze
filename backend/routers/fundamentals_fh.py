"""
Alternate fundamentals route using Finnhub — test at /api/fundamentals-fh/{symbol}
before switching from the Yahoo Finance route.
"""

import logging
from fastapi import APIRouter, HTTPException
from finnhub_client import fetch_metrics, fh_get

router = APIRouter()
logger = logging.getLogger(__name__)


def _f(v):
    try:
        f = float(v)
        import math
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _pct(v):
    """Finnhub returns some margins/rates as percentages (0–100) — normalise to 0–1."""
    f = _f(v)
    return f / 100 if f is not None else None


@router.get("/api/fundamentals-fh/{symbol}")
async def get_fundamentals_fh(symbol: str):
    sym = symbol.upper()
    try:
        m, series = fetch_metrics(sym)
        profile   = fh_get("/stock/profile2", {"symbol": sym})

        metrics = {
            # Valuation
            "market_cap":         _f(m.get("marketCapitalization", 0)) * 1_000_000
                                   if m.get("marketCapitalization") else None,
            "enterprise_value":   None,  # not in free metric endpoint
            "pe_trailing":        _f(m.get("peBasicExclExtraTTM")),
            "pe_forward":         _f(m.get("peNormalizedAnnual")),
            "peg_ratio":          None,
            "ps_ratio":           _f(m.get("psAnnual")),
            "pb_ratio":           _f(m.get("pbAnnual")),
            "ev_ebitda":          _f(m.get("evEbitdaAnnual")),
            # Per-share
            "eps_trailing":       _f(m.get("epsBasicExclExtraTTM")),
            "eps_forward":        _f(m.get("epsNormalizedAnnual")),
            "book_value":         _f(m.get("bookValuePerShareAnnual")),
            "revenue_per_share":  _f(m.get("revenuePerShareTTM")),
            # Income (Finnhub free tier doesn't expose TTM revenue in metrics)
            "revenue_ttm":        None,
            "gross_profit":       None,
            "ebitda":             None,
            "net_income":         None,
            "free_cashflow":      None,
            "operating_cashflow": None,
            "total_cash":         None,
            "total_debt":         None,
            # Growth (returned as percentage, e.g. 12.5 = 12.5% → normalise to 0.125)
            "revenue_growth":     _pct(m.get("revenueGrowthTTMYoy")),
            "earnings_growth":    _pct(m.get("epsGrowthTTMYoy")),
            "earnings_qoq":       _pct(m.get("epsGrowthQuarterlyYoy")),
            # Margins (returned as percentages)
            "gross_margin":       _pct(m.get("grossMarginTTM")),
            "operating_margin":   _pct(m.get("operatingMarginTTM")),
            "profit_margin":      _pct(m.get("netMarginTTM")),
            # Returns
            "roe":                _pct(m.get("roeTTM")),
            "roa":                _pct(m.get("roaTTM")),
            # Balance-sheet ratios
            "debt_to_equity":     _f(m.get("totalDebt/totalEquityAnnual")),
            "current_ratio":      _f(m.get("currentRatioAnnual")),
            "quick_ratio":        _f(m.get("quickRatioAnnual")),
            # Market data
            "beta":               _f(m.get("beta")),
            "week52_high":        _f(m.get("52WeekHigh")),
            "week52_low":         _f(m.get("52WeekLow")),
            "avg_volume":         (_f(m.get("10DayAverageTradingVolume")) or 0) * 1_000_000,
            "shares_outstanding": None,
            "float_shares":       None,
            "held_insiders":      None,
            "held_institutions":  None,
            "short_ratio":        _f(m.get("shortInterestRatio")),
            "short_pct_float":    None,
            "dividend_yield":     _pct(m.get("dividendYieldIndicatedAnnual")),
            "payout_ratio":       _pct(m.get("payoutRatioAnnual")),
            # Analyst (not in Finnhub free metrics — use analyst router instead)
            "target_price":       None,
            "target_high":        None,
            "target_low":         None,
            "recommendation":     None,
            "num_analysts":       None,
            # Identity
            "name":               profile.get("name"),
            "sector":             profile.get("finnhubIndustry"),
            "industry":           profile.get("finnhubIndustry"),
        }

        # ── EPS quarterly series ───────────────────────────────────────
        earnings = []
        eps_series = (series.get("quarterly") or {}).get("eps") or []
        for entry in eps_series[-8:]:
            date_str = entry.get("period", "")
            actual   = _f(entry.get("v"))
            if actual is not None:
                earnings.append({
                    "date":         date_str,
                    "eps_actual":   actual,
                    "eps_estimate": None,
                    "surprise_pct": None,
                })

        return {
            "symbol":    sym,
            "source":    "finnhub",
            "metrics":   metrics,
            "quarterly": [],     # quarterly revenue/income not in free tier
            "earnings":  earnings,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Finnhub fundamentals error for %s: %s", sym, e)
        raise HTTPException(status_code=500, detail=str(e))
