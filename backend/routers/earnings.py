"""
SEC EDGAR earnings — two-step API.
1. GET /api/earnings/{symbol}                       → filing list, fast, no AI, cached 24h
2. GET /api/earnings/{symbol}/summary/{accession}   → AI prose via RAG, lazy, cached

RAG pipeline per filing:
  full HTML → strip → locate real MD&A section → chunk 700-char pieces
  → embed with all-MiniLM-L6-v2 → LanceDB in-memory → retrieve top chunks
  → focused context → gpt-5-mini summary
"""

import re
import logging
import os
import time
import asyncio
import traceback
from datetime import datetime, timedelta
from time import perf_counter
from fastapi import APIRouter, HTTPException
from openai import AzureOpenAI
import httpx

router  = APIRouter()
logger  = logging.getLogger(__name__)

_ai_client   = None
_embed_model = None                    # sentence-transformers, lazy-loaded
_cik_map:      dict[str, str]  = {}
_filing_cache: dict[str, dict] = {}   # sym → {data, filings_full, ts}
_summ_cache:   dict[str, str]  = {}   # accession → summary text
_CACHE_TTL = 86400

_UA = "JanStreet/1.0 (research tool)"

# RAG query strings — cover the five key analyst topics
_RAG_QUERIES = [
    "revenue earnings growth quarterly annual results",
    "gross margin operating margin profitability EBITDA",
    "guidance outlook forecast next quarter fiscal year",
    "business segment performance key developments acquisitions",
    "risks headwinds challenges competition regulatory export",
]


# ── AI client ────────────────────────────────────────────────────

def _ai() -> AzureOpenAI:
    global _ai_client
    if _ai_client is None:
        endpoint = os.getenv("GPT52_ENDPOINT")
        api_key  = os.getenv("GPT52_API_KEY")
        if not endpoint or not api_key:
            raise RuntimeError("GPT52_ENDPOINT / GPT52_API_KEY not set")
        _ai_client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=os.getenv("GPT52_API_VERSION", "2024-12-01-preview"),
        )
    return _ai_client


# ── Embedding model ──────────────────────────────────────────────

def _embedder():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformer model …")
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model ready.")
    return _embed_model


# ── RAG helpers ──────────────────────────────────────────────────

def _chunk_text(text: str, size: int = 700, overlap: int = 120) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start: start + size].strip()
        if len(chunk) > 80:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def _rag_context(full_mda: str) -> str:
    """
    Chunk the full MD&A, embed with sentence-transformers, run cosine-similarity
    search for five analyst-topic queries, return top-N unique chunks.
    For this scale (50-200 chunks) numpy dot-product search is instant.
    """
    import numpy as np

    t0     = perf_counter()
    chunks = _chunk_text(full_mda)
    if not chunks:
        logger.warning("RAG: no chunks produced — falling back to raw text[:12000]")
        return full_mda[:12000]

    chunks = chunks[:200]
    logger.debug("RAG: %d chunks from %d chars", len(chunks), len(full_mda))

    model = _embedder()

    t_embed = perf_counter()
    chunk_mat = model.encode(chunks, batch_size=64, show_progress_bar=False)
    norms     = np.linalg.norm(chunk_mat, axis=1, keepdims=True)
    chunk_mat = chunk_mat / np.where(norms == 0, 1, norms)
    logger.debug(
        "RAG: embedded %d chunks in %.2fs  shape=%s",
        len(chunks), perf_counter() - t_embed, chunk_mat.shape,
    )

    t_search = perf_counter()
    seen, result_parts = set(), []
    for q in _RAG_QUERIES:
        q_vec  = model.encode([q], show_progress_bar=False)[0]
        q_vec  = q_vec / (np.linalg.norm(q_vec) or 1.0)
        scores = chunk_mat @ q_vec
        for idx in np.argsort(scores)[::-1][:3]:
            txt = chunks[idx].strip()
            if txt not in seen:
                seen.add(txt)
                result_parts.append(txt)

    context_chars = sum(len(p) for p in result_parts)
    logger.info(
        "RAG: %d chunks → %d retrieved (%d chars context) in %.2fs total",
        len(chunks), len(result_parts), context_chars, perf_counter() - t0,
        extra={"chunks": len(chunks)},
    )
    return "\n\n---\n\n".join(result_parts)


# ── EDGAR helpers ─────────────────────────────────────────────────

async def _get_cik(ticker: str) -> str | None:
    global _cik_map
    if not _cik_map:
        logger.info("Loading SEC company_tickers.json …")
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers={"User-Agent": _UA},
            )
            r.raise_for_status()
            for entry in r.json().values():
                t = entry.get("ticker", "").upper()
                if t:
                    _cik_map[t] = str(entry["cik_str"]).zfill(10)
    return _cik_map.get(ticker.upper())


async def _recent_filings(cik: str) -> list[dict]:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(url, headers={"User-Agent": _UA, "Host": "data.sec.gov"})
        r.raise_for_status()
        data = r.json()

    recent       = data.get("filings", {}).get("recent", {})
    forms        = recent.get("form",            [])
    dates        = recent.get("filingDate",      [])
    accessions   = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    cutoff = datetime.now() - timedelta(days=450)
    results, counts = [], {"10-Q": 0, "10-K": 0}
    limits = {"10-Q": 4, "10-K": 1}

    for i, form in enumerate(forms):
        if form not in ("10-Q", "10-K"):
            continue
        if counts.get(form, 0) >= limits[form]:
            continue
        try:
            if datetime.strptime(dates[i], "%Y-%m-%d") < cutoff:
                break
        except ValueError:
            pass
        results.append({
            "form":        form,
            "date":        dates[i],
            "accession":   accessions[i],
            "primary_doc": primary_docs[i],
            "cik_int":     str(int(cik)),
        })
        counts[form] += 1

    return results


async def _fetch_full_mda(filing: dict) -> str:
    """Download the filing HTML and extract the complete MD&A section."""
    acc      = filing["accession"]
    acc_flat = acc.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{filing['cik_int']}/{acc_flat}/{filing['primary_doc']}"
    )
    logger.info(
        "Fetching SEC filing  acc=%s  doc=%s  url=%s",
        acc, filing["primary_doc"], url,
    )
    t0 = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": _UA})
            r.raise_for_status()
            raw = r.text
    except Exception as e:
        logger.error("SEC fetch failed  acc=%s  error=%s", acc, e)
        return ""

    fetch_ms = round((perf_counter() - t0) * 1000)
    logger.info(
        "SEC fetch OK  acc=%s  raw_html=%d chars  [%dms]",
        acc, len(raw), fetch_ms,
    )

    # Strip HTML tags and decode common HTML entities
    t1   = perf_counter()
    text = re.sub(r"<[^>]{1,4000}>", " ", raw)
    text = text.replace("&#8220;", '"').replace("&#8221;", '"').replace("&#8217;", "'")
    text = text.replace("&#8212;", "—").replace("&#160;", " ")
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    logger.debug(
        "HTML stripped  acc=%s  clean_chars=%d  [%.2fs]",
        acc, len(text), perf_counter() - t1,
    )

    # Skip first 20% to avoid Table-of-Contents false matches
    body_start = len(text) // 5
    lo_body    = text[body_start:].lower()

    mda_offset, matched_pat = None, None
    for pat in [
        r"management.s discussion and analysis",
        r"item\s+2[\.\s]", r"item\s+7[\.\s]",
        r"results of operations", r"business overview",
        r"financial highlights", r"overview",
    ]:
        m = re.search(pat, lo_body)
        if m:
            mda_offset, matched_pat = m.start(), pat
            break

    if mda_offset is None:
        logger.warning("MD&A section not found  acc=%s — using middle-third fallback", acc)
        start   = len(text) // 3
        section = text[start: start + 50000]
    else:
        abs_start    = body_start + mda_offset
        search_after = abs_start + 1000
        lo_after     = text[search_after:].lower()
        end_offset   = len(lo_after)
        end_pat      = None
        for pat in [
            r"item\s+7a[\.\s]",
            r"quantitative and qualitative disclosures about market",
            r"\bitem\s+8[\.\s]",
            r"financial statements and supplementary",
        ]:
            m = re.search(pat, lo_after)
            if m and m.start() < end_offset:
                end_offset, end_pat = m.start(), pat
        section = text[abs_start: search_after + end_offset]
        logger.debug(
            "MD&A boundaries  acc=%s  start_pat=%r  end_pat=%r  raw_section=%d chars",
            acc, matched_pat, end_pat, len(section),
        )

    section = re.sub(r"[^\x20-\x7E\n]", " ", section)
    section = re.sub(r" {2,}", " ", section).strip()
    logger.info(
        "MD&A extracted  acc=%s  chars=%d  est_chunks=%d  total_time=%.2fs",
        acc, len(section), len(section) // 580, perf_counter() - t0,
        extra={"accession": acc, "chars": len(section)},
    )
    return section


# ── AI analysis ───────────────────────────────────────────────────

def _summarise_one(full_mda: str, symbol: str, filing: dict) -> str:
    """RAG → focused context → AI summary."""
    deployment = os.getenv("GPT52_DEPLOYMENT", "gpt-4.1")
    label      = f"{filing['form']} filed {filing['date']}"
    acc        = filing["accession"]
    t_total    = perf_counter()

    # ── Stage 1: RAG retrieval ────────────────────────────────────
    try:
        context = _rag_context(full_mda)
    except Exception as exc:
        logger.warning(
            "RAG failed  acc=%s  error=%s — falling back to raw text[:12000]", acc, exc,
        )
        context = full_mda[:12000]

    logger.info(
        "RAG context ready  acc=%s  context_chars=%d", acc, len(context),
        extra={"accession": acc, "chars": len(context)},
    )

    # ── Stage 2: AI call ──────────────────────────────────────────
    prompt = (
        f"You are a sell-side equity analyst. Below are the most relevant excerpts "
        f"from {symbol}'s {label} MD&A.\n\n"
        f"{context}\n\n"
        "Produce a structured analyst briefing using the exact sections and format below. "
        "Each bullet must include specific numbers, percentages, or dollar figures where available.\n\n"
        "## Revenue & Earnings\n"
        "- <bullet with specific figures>\n\n"
        "## Segment Performance\n"
        "- <bullet per major segment>\n\n"
        "## Margins & Cash Flow\n"
        "- <bullet with margin %s and cash figures>\n\n"
        "## Guidance & Outlook\n"
        "- <bullet on forward guidance>\n\n"
        "## Key Risks\n"
        "- <bullet per risk>\n\n"
        "Use short, punchy bullets. Include actual numbers. No prose paragraphs."
    )
    logger.debug(
        "AI prompt built  acc=%s  prompt_chars=%d  (~%d tokens)",
        acc, len(prompt), len(prompt) // 4,
    )

    t_ai = perf_counter()
    resp = _ai().chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=5000,
    )
    ai_ms = round((perf_counter() - t_ai) * 1000)

    reasoning  = getattr(resp.usage.completion_tokens_details, "reasoning_tokens", 0)
    output_tok = resp.usage.completion_tokens - reasoning
    summary    = (resp.choices[0].message.content or "").strip()

    logger.info(
        "AI call done  acc=%s  finish=%s  reasoning=%d  output=%d  total_tokens=%d  [%dms]",
        acc, resp.choices[0].finish_reason, reasoning, output_tok,
        resp.usage.total_tokens, ai_ms,
        extra={
            "accession": acc, "reasoning_tokens": reasoning,
            "output_tokens": output_tok, "total_tokens": resp.usage.total_tokens,
            "duration_ms": ai_ms,
        },
    )
    logger.info(
        "Summary pipeline done  acc=%s  summary_chars=%d  total_time=%.2fs",
        acc, len(summary), perf_counter() - t_total,
    )
    return summary


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/api/earnings/{symbol}")
async def earnings_filings(symbol: str):
    """Return filing metadata only — fast, no AI."""
    sym = symbol.upper()

    cached = _filing_cache.get(sym)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        logger.info("Earnings filing cache hit: %s", sym)
        return cached["data"]

    try:
        cik = await _get_cik(sym)
        if not cik:
            raise HTTPException(404, f"No SEC CIK for {sym} — may not file with the SEC")

        filings = await _recent_filings(cik)
        if not filings:
            raise HTTPException(404, f"No 10-Q / 10-K found for {sym} in the last 15 months")

        result = {
            "symbol":    sym,
            "filings":   [{"form": f["form"], "date": f["date"], "accession": f["accession"]}
                          for f in filings],
            "cached_at": datetime.utcnow().isoformat(),
        }
        _filing_cache[sym] = {"data": result, "filings_full": filings, "ts": time.time()}
        logger.info("Earnings filings loaded for %s: %d filings", sym, len(filings))
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Earnings list error for %s:\n%s", sym, traceback.format_exc())
        raise HTTPException(500, f"Could not load filing list: {exc}")


@router.get("/api/earnings/{symbol}/summary/{accession}")
async def earnings_filing_summary(symbol: str, accession: str):
    """RAG-powered AI prose summary for one filing — lazy, cached per-accession."""
    sym = symbol.upper()

    if accession in _summ_cache:
        logger.info("Earnings summary cache hit: %s / %s", sym, accession)
        return {"summary": _summ_cache[accession]}

    cached = _filing_cache.get(sym)
    if not cached:
        await earnings_filings(sym)
        cached = _filing_cache.get(sym)

    filings_full = (cached or {}).get("filings_full", [])
    filing = next((f for f in filings_full if f["accession"] == accession), None)
    if not filing:
        raise HTTPException(404, "Filing not found — reload the filing list first")

    try:
        full_mda = await _fetch_full_mda(filing)
        if not full_mda:
            raise HTTPException(500, "Could not extract text from this filing")

        summary = await asyncio.to_thread(_summarise_one, full_mda, sym, filing)
        _summ_cache[accession] = summary
        logger.info("Earnings RAG summary done: %s / %s", sym, accession)
        return {"summary": summary}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Earnings summary error for %s/%s:\n%s", sym, accession, traceback.format_exc())
        raise HTTPException(500, f"Earnings analysis failed: {exc}")
