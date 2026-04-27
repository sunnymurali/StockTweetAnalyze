import math
import logging
from fastapi import APIRouter, HTTPException
import yfinance as yf

router = APIRouter()
logger = logging.getLogger(__name__)


def _f(v):
    """Convert any value to float or None, stripping NaN/Inf."""
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _s(v):
    return str(v) if v is not None else None


@router.get("/api/fundamentals/{symbol}")
async def get_fundamentals(symbol: str):
    sym = symbol.upper()
    try:
        tk   = yf.Ticker(sym)
        info = tk.info or {}

        def g(key): return _f(info.get(key))
        def s(key): return _s(info.get(key))

        metrics = {
            # Valuation
            "market_cap":        g("marketCap"),
            "enterprise_value":  g("enterpriseValue"),
            "pe_trailing":       g("trailingPE"),
            "pe_forward":        g("forwardPE"),
            "peg_ratio":         g("pegRatio"),
            "ps_ratio":          g("priceToSalesTrailingTwelveMonths"),
            "pb_ratio":          g("priceToBook"),
            "ev_ebitda":         g("enterpriseToEbitda"),
            # Per-share
            "eps_trailing":      g("trailingEps"),
            "eps_forward":       g("forwardEps"),
            "book_value":        g("bookValue"),
            "revenue_per_share": g("revenuePerShare"),
            # Income
            "revenue_ttm":       g("totalRevenue"),
            "gross_profit":      g("grossProfits"),
            "ebitda":            g("ebitda"),
            "net_income":        g("netIncomeToCommon"),
            "free_cashflow":     g("freeCashflow"),
            "operating_cashflow":g("operatingCashflow"),
            "total_cash":        g("totalCash"),
            "total_debt":        g("totalDebt"),
            # Growth
            "revenue_growth":    g("revenueGrowth"),
            "earnings_growth":   g("earningsGrowth"),
            "earnings_qoq":      g("earningsQuarterlyGrowth"),
            # Margins
            "gross_margin":      g("grossMargins"),
            "operating_margin":  g("operatingMargins"),
            "profit_margin":     g("profitMargins"),
            # Returns
            "roe":               g("returnOnEquity"),
            "roa":               g("returnOnAssets"),
            # Balance-sheet ratios
            "debt_to_equity":    g("debtToEquity"),
            "current_ratio":     g("currentRatio"),
            "quick_ratio":       g("quickRatio"),
            # Market data
            "beta":              g("beta"),
            "week52_high":       g("fiftyTwoWeekHigh"),
            "week52_low":        g("fiftyTwoWeekLow"),
            "avg_volume":        g("averageVolume"),
            "shares_outstanding":g("sharesOutstanding"),
            "float_shares":      g("floatShares"),
            "held_insiders":     g("heldPercentInsiders"),
            "held_institutions": g("heldPercentInstitutions"),
            "short_ratio":       g("shortRatio"),
            "short_pct_float":   g("shortPercentOfFloat"),
            "dividend_yield":    g("dividendYield"),
            "payout_ratio":      g("payoutRatio"),
            # Analyst
            "target_price":      g("targetMeanPrice"),
            "target_high":       g("targetHighPrice"),
            "target_low":        g("targetLowPrice"),
            "recommendation":    s("recommendationKey"),
            "num_analysts":      g("numberOfAnalystOpinions"),
            # Identity
            "name":              s("longName") or s("shortName"),
            "sector":            s("sector"),
            "industry":          s("industry"),
        }

        # ── Quarterly revenue / net-income ────────────────────────
        quarterly = []
        try:
            stmt = tk.quarterly_income_stmt
            if stmt is not None and not stmt.empty:
                idx = [str(k).lower() for k in stmt.index]
                rev_key = next((stmt.index[i] for i, k in enumerate(idx)
                                if "revenue" in k and "total" in k), None)
                ni_key  = next((stmt.index[i] for i, k in enumerate(idx)
                                if "net income" in k), None)
                gp_key  = next((stmt.index[i] for i, k in enumerate(idx)
                                if "gross profit" in k), None)

                for col in reversed(stmt.columns[:8]):   # oldest → newest
                    ds = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
                    quarterly.append({
                        "date":        ds,
                        "revenue":     _f(stmt.at[rev_key, col]) if rev_key else None,
                        "net_income":  _f(stmt.at[ni_key,  col]) if ni_key  else None,
                        "gross_profit":_f(stmt.at[gp_key,  col]) if gp_key  else None,
                    })
        except Exception as e:
            logger.warning("quarterly_income_stmt failed for %s: %s", sym, e)

        # ── EPS history (actual vs estimate) ──────────────────────
        earnings = []
        try:
            eh = tk.earnings_history
            if eh is not None and not eh.empty:
                for idx, row in eh.tail(8).iterrows():
                    ds  = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                    d   = dict(row)
                    est = _f(d.get("EPS Estimate")  or d.get("epsEstimate"))
                    act = _f(d.get("Reported EPS")  or d.get("epsActual"))
                    surp= _f(d.get("Surprise(%)")   or d.get("surprisePercent"))
                    earnings.append({
                        "date":         ds,
                        "eps_estimate": est,
                        "eps_actual":   act,
                        "surprise_pct": surp,
                    })
        except Exception as e:
            logger.warning("earnings_history failed for %s: %s", sym, e)

        return {"symbol": sym, "metrics": metrics,
                "quarterly": quarterly, "earnings": earnings}

    except Exception as e:
        logger.error("Fundamentals error for %s: %s", sym, e)
        raise HTTPException(status_code=500, detail=str(e))
