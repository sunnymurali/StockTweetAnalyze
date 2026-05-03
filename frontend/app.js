"use strict";

const { useState, useEffect, useRef, useCallback } = React;
const API = "";

const SECTORS = [
  { name: "Technology",       ticker: "XLK" },
  { name: "Financials",       ticker: "XLF" },
  { name: "Health Care",      ticker: "XLV" },
  { name: "Consumer Disc.",   ticker: "XLY" },
  { name: "Comm. Services",   ticker: "XLC" },
  { name: "Industrials",      ticker: "XLI" },
  { name: "Consumer Staples", ticker: "XLP" },
  { name: "Energy",           ticker: "XLE" },
  { name: "Utilities",        ticker: "XLU" },
  { name: "Real Estate",      ticker: "XLRE" },
  { name: "Materials",        ticker: "XLB" },
];

// ─── Utilities ────────────────────────────────────────────────────

function cleanHandle(h) {
  if (!h) return "";
  return h.startsWith("@") ? h.slice(1) : h;
}

function fmtPrice(n) {
  if (n == null) return "—";
  return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(n, withSign = true) {
  if (n == null) return "—";
  const s = withSign && n >= 0 ? "+" : "";
  return s + Number(n).toFixed(2) + "%";
}

function fmtNum(n) {
  if (n == null || n === "") return "—";
  if (Math.abs(n) >= 1e12) return (n / 1e12).toFixed(2) + "T";
  if (Math.abs(n) >= 1e9)  return (n / 1e9).toFixed(2)  + "B";
  if (Math.abs(n) >= 1e6)  return (n / 1e6).toFixed(1)  + "M";
  if (Math.abs(n) >= 1e3)  return (n / 1e3).toFixed(1)  + "K";
  return String(n);
}

function fmtMktCap(n) {
  if (!n) return "—";
  if (n >= 1e12) return "$" + (n / 1e12).toFixed(2) + "T";
  if (n >= 1e9)  return "$" + (n / 1e9).toFixed(1)  + "B";
  return "$" + fmtNum(n);
}

function fmtDate(s) {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d)) return String(s).slice(0, 16);
  const diff = (Date.now() - d) / 1000;
  if (diff < 3600)  return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtQuarterLabel(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr.slice(0, 7);
  const q = Math.floor(d.getMonth() / 3) + 1;
  return `Q${q}'${String(d.getFullYear()).slice(2)}`;
}

const AVATAR_COLORS = [
  "#4f46e5","#0891b2","#059669","#d97706","#dc2626","#7c3aed","#db2777","#0284c7",
];
function avatarColor(h) {
  let n = 0;
  for (const c of String(h)) n = (n * 31 + c.charCodeAt(0)) & 0xffffff;
  return AVATAR_COLORS[Math.abs(n) % AVATAR_COLORS.length];
}

// ─── Seeded sparkline ─────────────────────────────────────────────

function seededRng(seed) {
  let s = seed >>> 0;
  return () => { s = (Math.imul(1664525, s) + 1013904223) | 0; return (s >>> 0) / 4294967295; };
}

function Sparkline({ ticker }) {
  const seed = Array.from(ticker).reduce((a, c) => a * 31 + c.charCodeAt(0), 1);
  const rng = seededRng(seed);
  const n = 12, w = 36, h = 14;
  const vals = Array.from({ length: n }, () => rng());
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const pts = vals.map((v, i) =>
    `${(i / (n - 1)) * w},${h - ((v - min) / range) * (h - 3) - 1}`
  ).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: "block", flexShrink: 0 }}>
      <polyline points={pts} fill="none"
        stroke={vals[n - 1] >= vals[0] ? "var(--ts-up)" : "var(--ts-down)"}
        strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ─── Typewriter hook ──────────────────────────────────────────────

function useTypewriter(text, speed = 16) {
  const [shown, setShown] = useState("");
  useEffect(() => {
    if (!text) { setShown(""); return; }
    setShown("");
    let i = 0;
    const id = setInterval(() => { i++; setShown(text.slice(0, i)); if (i >= text.length) clearInterval(id); }, speed);
    return () => clearInterval(id);
  }, [text]);
  return shown;
}

// ─── TopBar ───────────────────────────────────────────────────────

function TopBar({ count }) {
  const [time, setTime] = useState(() => new Date().toLocaleTimeString("en-US", { hour12: false }));
  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString("en-US", { hour12: false })), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="ts-topbar">
      <div className="ts-logo">
        <span className="ts-logo-mark">JT</span>
        <span className="ts-logo-text">Jan<span>Tweet</span></span>
      </div>
      <div className="ts-topbar-center" />
      <div className="ts-topbar-right">
        <span className="ts-market-status ts-mono">
          <span style={{ width:7,height:7,borderRadius:"50%",background:"var(--ts-up)",display:"inline-block" }} />
          LIVE
        </span>
        <span className="ts-mono" style={{ fontSize:11, color:"rgba(255,255,255,0.75)" }}>{time}</span>
        <span className="ts-mono" style={{ fontSize:10,color:"rgba(255,255,255,0.90)",background:"rgba(255,255,255,0.15)",padding:"2px 10px",borderRadius:20 }}>
          {count} tweets
        </span>
      </div>
    </div>
  );
}

// ─── Tweet Feed ───────────────────────────────────────────────────

function TweetFeed({ tweets, activeId, onSelect, loading, search, onSearch, pendingCount, onLoadPending, lastRefreshed }) {
  return (
    <div className="ts-feed">
      <div className="ts-feed-header">
        <div className="ts-feed-title-row">
          <div className="ts-feed-title">FEED</div>
          <span className="ts-feed-count">{tweets.length}</span>
          {lastRefreshed && (
            <span style={{ fontFamily:"var(--ts-mono)", fontSize:9, color:"var(--ts-dim)", marginLeft:"auto" }}>
              {fmtDate(lastRefreshed)}
            </span>
          )}
        </div>
        <input className="ts-feed-search" placeholder="Ticker (e.g. NVDA) or keyword…"
          value={search} onChange={e => onSearch(e.target.value)} />
      </div>
      {pendingCount > 0 && (
        <button className="ts-new-banner" onClick={onLoadPending}>
          ↑ {pendingCount} new tweet{pendingCount > 1 ? "s" : ""} — click to load
        </button>
      )}
      <div className="ts-feed-scroll">
        {loading && <div className="ts-feed-empty">Loading feed…</div>}
        {!loading && !tweets.length && <div className="ts-feed-empty">No tweets found.</div>}
        {tweets.map(t => (
          <TweetCard key={t.id} tweet={t} isActive={activeId === t.id} onSelect={onSelect} />
        ))}
      </div>
    </div>
  );
}

function TweetCard({ tweet, isActive, onSelect }) {
  const handle = cleanHandle(tweet.author || "");
  const bg  = avatarColor(handle || "x");
  const ini = (handle || "?")[0].toUpperCase();
  return (
    <div className={`ts-tweet${isActive ? " is-new" : ""}`}
      style={isActive ? { background:"var(--ts-surface)" } : {}}
      onClick={() => onSelect(tweet, tweet.tickers?.[0])}>
      <div className="ts-tweet-header">
        <div className="ts-avatar" style={{ background: bg }}>{ini}</div>
        <div className="ts-tweet-meta">
          <div className="ts-tweet-name-row">
            <span className="ts-tweet-name">TradingDesk</span>
            <span className="ts-tweet-handle">Feed</span>
          </div>
          <div className="ts-tweet-time-row">
            <span className="ts-tweet-time">{fmtDate(tweet.date)}</span>
          </div>
        </div>
      </div>
      {tweet.tickers?.length > 0 && (
        <div style={{ display:"flex", gap:4, flexWrap:"wrap" }}>
          {tweet.tickers.map(tk => (
            <span key={tk} className="ts-chip"
              onClick={e => { e.stopPropagation(); onSelect(tweet, tk); }}
              title={`Load $${tk}`}>
              <Sparkline ticker={tk} />
              <span className="ts-chip-symbol">${tk}</span>
            </span>
          ))}
        </div>
      )}
      <div className="ts-tweet-body" style={{ fontSize:12.5 }}>{tweet.text}</div>
    </div>
  );
}

// ─── Detail Panel (center) ────────────────────────────────────────

function DetailPanel({ symbol, quote, timespan, onTimespanChange, detailView, onDetailViewChange, fundamentals, fundLoading, news, earningsInfo }) {
  if (!symbol) {
    return (
      <div className="ts-detail">
        <div className="ts-empty">
          <div className="ts-empty-inner">
            <div className="ts-empty-icon">📈</div>
            <div className="ts-empty-title">SELECT A TWEET</div>
            <div className="ts-empty-desc">Click any tweet in the feed to load live price data, chart, and AI analysis.</div>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="ts-detail">
      <PriceHeader quote={quote} earningsInfo={earningsInfo} />
      <div className="ts-chart-bar">
        {detailView === "chart" ? (
          <div className="ts-tf-buttons">
            {[{key:"day",label:"1D"},{key:"week",label:"1W"},{key:"3y",label:"3Y"}].map(({key,label}) => (
              <button key={key} className={`ts-tf${timespan===key?" active":""}`}
                onClick={() => onTimespanChange(key)}>{label}</button>
            ))}
          </div>
        ) : (
          <span className="ts-mono" style={{ fontSize:10, color:"var(--ts-dim)" }}>
            {symbol} · {quote?.name || ""}
          </span>
        )}
        <div className="ts-view-tabs">
          <button className={`ts-view-tab${detailView==="chart"?" active":""}`}
            onClick={() => onDetailViewChange("chart")}>CHART</button>
          <button className={`ts-view-tab${detailView==="fundamentals"?" active":""}`}
            onClick={() => onDetailViewChange("fundamentals")}>FUNDMTLS</button>
          <button className={`ts-view-tab${detailView==="earnings"?" active":""}`}
            onClick={() => onDetailViewChange("earnings")}>EARNINGS</button>
          <button className={`ts-view-tab${detailView==="analyst"?" active":""}`}
            onClick={() => onDetailViewChange("analyst")}>ANALYST</button>
        </div>
      </div>
      <div className="ts-detail-scroll">
        {detailView === "chart"        && <TVChart symbol={symbol} timespan={timespan} />}
        {detailView === "fundamentals" && <FundamentalsPanel data={fundamentals} loading={fundLoading} />}
        {detailView === "earnings"     && <EarningsPanel symbol={symbol} />}
        {detailView === "analyst"      && <AnalystPanel symbol={symbol} currentPrice={quote?.price} />}
        <NewsRail articles={news || []} />
      </div>
    </div>
  );
}

// ─── Price Header ─────────────────────────────────────────────────

function EarningsBox({ info }) {
  if (!info?.earnings_date) return null;
  const d     = new Date(info.earnings_date);
  const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const days  = Math.round((d - Date.now()) / 86400000);
  const soon  = days >= 0 && days <= 14;
  return (
    <div className={`ts-earnings-box${soon ? " soon" : ""}`}>
      <span className="ts-earnings-label">EARNINGS</span>
      <span className="ts-earnings-date">{label}</span>
      {info.eps_avg != null && (
        <span className="ts-earnings-est">EPS est. ${info.eps_avg.toFixed(2)}</span>
      )}
    </div>
  );
}

function PriceHeader({ quote, earningsInfo }) {
  if (!quote) return (
    <div className="ts-price-header">
      <div style={{ color:"var(--ts-muted)", fontSize:12, fontFamily:"var(--ts-mono)" }}>Loading quote…</div>
    </div>
  );
  if (quote.error) return (
    <div className="ts-price-header">
      <div style={{ color:"var(--ts-down)", fontSize:12 }}>{quote.error}</div>
    </div>
  );
  const up = (quote.change_pct ?? 0) >= 0;
  const changeColor = up ? "var(--ts-up)" : "var(--ts-down)";
  return (
    <div className="ts-price-header">
      <div className="ts-price-id">
        <div className="ts-price-symbol-row">
          <span className="ts-price-symbol">{quote.symbol}</span>
          {quote.name && <span className="ts-price-name">{quote.name}</span>}
        </div>
        {quote.sector && <span className="ts-price-sector">{quote.sector}</span>}
      </div>
      <div className="ts-price-main">
        <div className="ts-price-value" style={{ color: changeColor }}>{fmtPrice(quote.price)}</div>
        <div className="ts-price-change">
          <span style={{ color: changeColor }}>
            {up ? "▲" : "▼"} {fmtPct(Math.abs(quote.change_pct ?? 0), false)}
          </span>
          <span style={{ color:"var(--ts-muted)" }}>today</span>
        </div>
      </div>
      <div className="ts-price-stats">
        {[
          ["HIGH", fmtPrice(quote.day_high)],
          ["LOW",  fmtPrice(quote.day_low)],
          ["VOL",  fmtNum(quote.volume)],
          ["MKT CAP", fmtMktCap(quote.market_cap)],
        ].map(([label, val]) => (
          <div key={label} className="ts-stat">
            <span className="ts-stat-label">{label}</span>
            <span className="ts-stat-value">{val}</span>
          </div>
        ))}
        <EarningsBox info={earningsInfo} />
      </div>
    </div>
  );
}

// ─── TradingView Chart ────────────────────────────────────────────

const TV_INTERVAL = { day: "5", week: "60", "3y": "W" };

function TVChart({ symbol, timespan }) {
  const idRef = useRef("tv_" + Math.random().toString(36).slice(2, 9));

  useEffect(() => {
    if (!symbol || !window.TradingView) return;
    const el = document.getElementById(idRef.current);
    if (!el) return;
    el.innerHTML = "";

    new window.TradingView.widget({
      autosize:          true,
      symbol:            symbol,
      interval:          TV_INTERVAL[timespan] || "D",
      timezone:          "America/New_York",
      theme:             "dark",
      style:             "1",
      locale:            "en",
      toolbar_bg:        "#0d0d0d",
      enable_publishing: false,
      hide_top_toolbar:  false,
      save_image:        false,
      container_id:      idRef.current,
      studies:           ["RSI@tv-basicstudies", "MACD@tv-basicstudies"],
      overrides: {
        "paneProperties.background":                          "#07080f",
        "paneProperties.backgroundType":                      "solid",
        "paneProperties.vertGridProperties.color":            "#0f1525",
        "paneProperties.horzGridProperties.color":            "#0f1525",
        "scalesProperties.textColor":                         "#c0c8e0",
        "mainSeriesProperties.candleStyle.upColor":           "#00ff88",
        "mainSeriesProperties.candleStyle.downColor":         "#ff2d55",
        "mainSeriesProperties.candleStyle.borderUpColor":     "#00ff88",
        "mainSeriesProperties.candleStyle.borderDownColor":   "#ff2d55",
        "mainSeriesProperties.candleStyle.wickUpColor":       "#00ff88",
        "mainSeriesProperties.candleStyle.wickDownColor":     "#ff2d55",
      },
    });

    return () => { if (el) el.innerHTML = ""; };
  }, [symbol, timespan]);

  return (
    <div style={{ padding: 0, height: 500 }}>
      <div id={idRef.current} style={{ width: "100%", height: "100%" }} />
    </div>
  );
}

// ─── Fundamentals Panel ───────────────────────────────────────────

function KV({ label, value, colorClass = "" }) {
  return (
    <div className="ts-kv">
      <span className="ts-kv-label">{label}</span>
      <span className={`ts-kv-value${colorClass ? " " + colorClass : ""}`}>
        {value ?? "—"}
      </span>
    </div>
  );
}

function MarginBar({ label, value, color = "var(--ts-blue)" }) {
  if (value == null) return null;
  const pct = Math.min(Math.max(value * 100, -100), 100);
  const absPct = Math.abs(pct);
  const isNeg = pct < 0;
  const barColor = isNeg ? "var(--ts-down)" : color;
  return (
    <div className="ts-mrow">
      <span className="ts-mrow-label">{label}</span>
      <div className="ts-mrow-track">
        <div className="ts-mrow-fill" style={{ width: `${absPct}%`, background: barColor }} />
      </div>
      <span className={`ts-mrow-pct${isNeg ? " down" : ""}`} style={{ color: barColor }}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

// Simple SVG bar chart (horizontal flex of vertical bars)
function MiniBarChart({ items, color = "var(--ts-blue)", valueLabel = v => fmtNum(v) }) {
  if (!items.length) return null;
  const vals = items.map(d => d.value ?? 0);
  const maxV = Math.max(...vals.map(Math.abs)) || 1;
  const W = 100, H = 72, n = items.length, gap = 3;
  const barW = Math.max(4, Math.floor((W * 2.6 - gap * (n - 1)) / n));

  return (
    <svg width="100%" viewBox={`0 0 ${n * (barW + gap)} ${H + 20}`}
      style={{ overflow:"visible", display:"block" }}>
      {items.map((d, i) => {
        const v = d.value ?? 0;
        const barH = Math.max(2, (Math.abs(v) / maxV) * H);
        const x = i * (barW + gap);
        const y = H - barH;
        const col = v < 0 ? "var(--ts-down)" : color;
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={barH} fill={col} rx={2} opacity={0.82}>
              <title>{d.label}: {valueLabel(v)}</title>
            </rect>
            <text x={x + barW / 2} y={H + 14} textAnchor="middle"
              fontSize={8} fill="#6b7280" fontFamily="IBM Plex Mono,monospace">
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// EPS chart: actual bar coloured by beat/miss, thin line for estimate
function EpsChart({ earnings }) {
  if (!earnings.length) return null;
  const actuals = earnings.map(e => e.eps_actual ?? 0);
  const all     = earnings.flatMap(e => [e.eps_actual ?? 0, e.eps_estimate ?? 0]);
  const maxA    = Math.max(...all.map(Math.abs)) || 1;
  const W = 100, H = 72, n = earnings.length, gap = 3;
  const barW = Math.max(4, Math.floor((W * 2.6 - gap * (n - 1)) / n));
  const H_BASE = H; // y=0 is top, baseline at H for positive-only; handle negative with midpoint

  // Use midpoint baseline if any negatives
  const hasNeg = all.some(v => v < 0);
  const baseline = hasNeg ? H / 2 : H;

  return (
    <svg width="100%" viewBox={`0 0 ${n * (barW + gap)} ${H + 20}`}
      style={{ overflow:"visible", display:"block" }}>
      {/* zero line if mixed */}
      {hasNeg && <line x1={0} y1={baseline} x2={n*(barW+gap)} y2={baseline}
        stroke="#d2d6e4" strokeWidth={1} />}
      {earnings.map((e, i) => {
        const act = e.eps_actual ?? 0;
        const est = e.eps_estimate;
        const x   = i * (barW + gap);
        // bar height & y for actual
        const barH = Math.max(2, (Math.abs(act) / maxA) * (hasNeg ? H/2 : H));
        const y    = act >= 0 ? baseline - barH : baseline;
        const beat = est != null ? act >= est : true;
        const col  = beat ? "var(--ts-up)" : "var(--ts-down)";
        // estimate line y position
        const estY = est != null
          ? baseline - (est / maxA) * (hasNeg ? H/2 : H)
          : null;
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={barH} fill={col} rx={2} opacity={0.8}>
              <title>
                {e.date}: Actual {act.toFixed(2)}{est != null ? ` / Est ${est.toFixed(2)}` : ""}
                {e.surprise_pct != null ? ` (${e.surprise_pct > 0 ? "+" : ""}${e.surprise_pct.toFixed(1)}%)` : ""}
              </title>
            </rect>
            {estY != null && (
              <line x1={x} y1={estY} x2={x + barW} y2={estY}
                stroke="var(--ts-warn)" strokeWidth={1.5} strokeDasharray="2,2" />
            )}
            <text x={x + barW / 2} y={H + 14} textAnchor="middle"
              fontSize={8} fill="#6b7280" fontFamily="IBM Plex Mono,monospace">
              {fmtQuarterLabel(e.date)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function recClass(rec) {
  if (!rec) return "";
  const r = rec.toLowerCase();
  if (r.includes("strong_buy") || r.includes("strong buy")) return "ts-rec-strong-buy";
  if (r.includes("buy"))  return "ts-rec-buy";
  if (r.includes("sell")) return "ts-rec-sell";
  return "ts-rec-hold";
}

function recLabel(rec) {
  if (!rec) return "—";
  return rec.replace(/_/g, " ").toUpperCase();
}

function pctColor(v) {
  if (v == null) return "";
  return v >= 0 ? "up" : "down";
}

function FundamentalsPanel({ data, loading }) {
  if (loading) return (
    <div className="ts-fundm" style={{ display:"grid", placeItems:"center", color:"var(--ts-muted)", fontSize:12, fontFamily:"var(--ts-mono)" }}>
      Loading fundamentals…
    </div>
  );
  if (!data) return (
    <div className="ts-fundm" style={{ display:"grid", placeItems:"center", color:"var(--ts-muted)", fontSize:12 }}>
      No fundamentals data
    </div>
  );
  const m = data.metrics || {};
  const q = data.quarterly || [];
  const e = data.earnings  || [];

  const revenueItems = q.filter(d => d.revenue != null)
    .map(d => ({ label: fmtQuarterLabel(d.date), value: d.revenue }));
  const niItems = q.filter(d => d.net_income != null)
    .map(d => ({ label: fmtQuarterLabel(d.date), value: d.net_income }));

  return (
    <div className="ts-fundm">

      {/* ── VALUATION ─────────────────────── */}
      <div className="ts-fundm-section">
        <div className="ts-fundm-title">Valuation</div>
        <div className="ts-fundm-grid">
          <KV label="P/E (TTM)"     value={m.pe_trailing != null ? m.pe_trailing.toFixed(1) : null} />
          <KV label="P/E (Fwd)"     value={m.pe_forward  != null ? m.pe_forward.toFixed(1)  : null} />
          <KV label="PEG Ratio"     value={m.peg_ratio   != null ? m.peg_ratio.toFixed(2)   : null} />
          <KV label="P/S (TTM)"     value={m.ps_ratio    != null ? m.ps_ratio.toFixed(2)    : null} />
          <KV label="P/B Ratio"     value={m.pb_ratio    != null ? m.pb_ratio.toFixed(2)    : null} />
          <KV label="EV/EBITDA"     value={m.ev_ebitda   != null ? m.ev_ebitda.toFixed(1)   : null} />
        </div>
      </div>

      {/* ── EPS ───────────────────────────── */}
      <div className="ts-fundm-section">
        <div className="ts-fundm-title">Earnings Per Share</div>
        <div className="ts-fundm-grid">
          <KV label="EPS (TTM)"    value={m.eps_trailing != null ? "$" + m.eps_trailing.toFixed(2) : null} />
          <KV label="EPS (Fwd)"    value={m.eps_forward  != null ? "$" + m.eps_forward.toFixed(2)  : null} />
          <KV label="Book Value"   value={m.book_value   != null ? "$" + m.book_value.toFixed(2)   : null} />
          <KV label="Revenue / Sh" value={m.revenue_per_share != null ? "$" + m.revenue_per_share.toFixed(2) : null} />
          <KV label="Mkt Cap"      value={fmtMktCap(m.market_cap)} />
          <KV label="Ent. Value"   value={fmtMktCap(m.enterprise_value)} />
        </div>
      </div>

      {/* ── REVENUE & INCOME ──────────────── */}
      <div className="ts-fundm-section">
        <div className="ts-fundm-title">Revenue &amp; Income (TTM)</div>
        <div className="ts-fundm-grid" style={{ marginBottom: 10 }}>
          <KV label="Revenue"        value={fmtNum(m.revenue_ttm)} />
          <KV label="Gross Profit"   value={fmtNum(m.gross_profit)} />
          <KV label="EBITDA"         value={fmtNum(m.ebitda)} />
          <KV label="Net Income"     value={fmtNum(m.net_income)} />
          <KV label="Free Cash Flow" value={fmtNum(m.free_cashflow)} />
          <KV label="Op. Cash Flow"  value={fmtNum(m.operating_cashflow)} />
        </div>
      </div>

      {/* ── GROWTH ────────────────────────── */}
      <div className="ts-fundm-section">
        <div className="ts-fundm-title">Growth</div>
        <div className="ts-fundm-grid">
          <KV label="Revenue YoY"  value={m.revenue_growth  != null ? fmtPct(m.revenue_growth  * 100) : null}
            colorClass={pctColor(m.revenue_growth)} />
          <KV label="Earnings YoY" value={m.earnings_growth != null ? fmtPct(m.earnings_growth * 100) : null}
            colorClass={pctColor(m.earnings_growth)} />
          <KV label="Earnings QoQ" value={m.earnings_qoq   != null ? fmtPct(m.earnings_qoq    * 100) : null}
            colorClass={pctColor(m.earnings_qoq)} />
        </div>
      </div>

      {/* ── PROFITABILITY MARGINS ─────────── */}
      <div className="ts-fundm-section">
        <div className="ts-fundm-title">Profitability</div>
        <MarginBar label="Gross Margin"     value={m.gross_margin}     color="var(--ts-blue)" />
        <MarginBar label="Operating Margin" value={m.operating_margin} color="var(--ts-accent)" />
        <MarginBar label="Net Margin"       value={m.profit_margin}    color="var(--ts-up)" />
        <MarginBar label="ROE"              value={m.roe}              color="var(--ts-blue)" />
        <MarginBar label="ROA"              value={m.roa}              color="var(--ts-accent)" />
      </div>

      {/* ── BALANCE SHEET ─────────────────── */}
      <div className="ts-fundm-section">
        <div className="ts-fundm-title">Balance Sheet</div>
        <div className="ts-fundm-grid">
          <KV label="Total Cash"   value={fmtNum(m.total_cash)} />
          <KV label="Total Debt"   value={fmtNum(m.total_debt)} />
          <KV label="Debt / Equity" value={m.debt_to_equity != null ? m.debt_to_equity.toFixed(2) : null} />
          <KV label="Current Ratio" value={m.current_ratio  != null ? m.current_ratio.toFixed(2)  : null} />
          <KV label="Quick Ratio"   value={m.quick_ratio    != null ? m.quick_ratio.toFixed(2)    : null} />
        </div>
      </div>

      {/* ── MARKET DATA ───────────────────── */}
      <div className="ts-fundm-section">
        <div className="ts-fundm-title">Market Data</div>
        <div className="ts-fundm-grid">
          <KV label="Beta"          value={m.beta        != null ? m.beta.toFixed(2) : null} />
          <KV label="52W High"      value={fmtPrice(m.week52_high)} />
          <KV label="52W Low"       value={fmtPrice(m.week52_low)} />
          <KV label="Avg Volume"    value={fmtNum(m.avg_volume)} />
          <KV label="Shares Out."   value={fmtNum(m.shares_outstanding)} />
          <KV label="Float"         value={fmtNum(m.float_shares)} />
          <KV label="% Insiders"    value={m.held_insiders     != null ? (m.held_insiders     * 100).toFixed(1) + "%" : null} />
          <KV label="% Institutions"value={m.held_institutions != null ? (m.held_institutions * 100).toFixed(1) + "%" : null} />
          <KV label="Short Ratio"   value={m.short_ratio != null ? m.short_ratio.toFixed(2) : null} />
          <KV label="Dividend Yield"value={m.dividend_yield != null ? (m.dividend_yield * 100).toFixed(2) + "%" : null} />
          <KV label="Payout Ratio"  value={m.payout_ratio   != null ? (m.payout_ratio   * 100).toFixed(1) + "%" : null} />
        </div>
      </div>

      {/* ── ANALYST ───────────────────────── */}
      <div className="ts-fundm-section">
        <div className="ts-fundm-title">Analyst Consensus</div>
        <div style={{ display:"flex", gap:16, alignItems:"center", marginBottom:10 }}>
          {m.recommendation && (
            <span className={`ts-rec-badge ${recClass(m.recommendation)}`}>
              {recLabel(m.recommendation)}
            </span>
          )}
          {m.num_analysts != null && (
            <span style={{ fontFamily:"var(--ts-mono)", fontSize:10, color:"var(--ts-muted)" }}>
              {Math.round(m.num_analysts)} analysts
            </span>
          )}
        </div>
        <div className="ts-fundm-grid">
          <KV label="Target (Mean)" value={fmtPrice(m.target_price)} />
          <KV label="Target (High)" value={fmtPrice(m.target_high)} />
          <KV label="Target (Low)"  value={fmtPrice(m.target_low)} />
        </div>
      </div>

      {/* ── QUARTERLY REVENUE ─────────────── */}
      {revenueItems.length > 0 && (
        <div className="ts-fundm-section">
          <div className="ts-fundm-title">Quarterly Revenue</div>
          <MiniBarChart items={revenueItems} color="var(--ts-blue)"
            valueLabel={v => "$" + fmtNum(v)} />
        </div>
      )}

      {/* ── QUARTERLY NET INCOME ──────────── */}
      {niItems.length > 0 && (
        <div className="ts-fundm-section">
          <div className="ts-fundm-title">Quarterly Net Income</div>
          <MiniBarChart items={niItems}
            color="var(--ts-up)"
            valueLabel={v => "$" + fmtNum(v)} />
        </div>
      )}

      {/* ── EPS: ACTUAL vs ESTIMATE ───────── */}
      {e.length > 0 && (
        <div className="ts-fundm-section">
          <div className="ts-fundm-title" style={{ marginBottom:4 }}>
            EPS: Actual vs Estimate
          </div>
          <div style={{ fontFamily:"var(--ts-mono)", fontSize:9, color:"var(--ts-muted)", marginBottom:8 }}>
            <span style={{ borderBottom:"1.5px dashed var(--ts-warn)", paddingBottom:1 }}>— dashed = estimate</span>
            &nbsp;&nbsp;
            <span style={{ color:"var(--ts-up)" }}>■ beat</span>
            &nbsp;
            <span style={{ color:"var(--ts-down)" }}>■ miss</span>
          </div>
          <EpsChart earnings={e} />
        </div>
      )}
    </div>
  );
}

// ─── Markdown renderer (## headers + - bullets only) ─────────────

function EarningsMd({ text }) {
  if (!text) return null;
  const nodes = [];
  let bulletBuffer = [];

  const flushBullets = () => {
    if (!bulletBuffer.length) return;
    nodes.push(
      <ul key={nodes.length} className="ts-earn-bullets">
        {bulletBuffer.map((b, i) => <li key={i}>{b}</li>)}
      </ul>
    );
    bulletBuffer = [];
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith("## ")) {
      flushBullets();
      nodes.push(
        <div key={nodes.length} className="ts-earn-section-header">
          {line.slice(3)}
        </div>
      );
    } else if (line.startsWith("- ")) {
      bulletBuffer.push(line.slice(2));
    } else {
      flushBullets();
      nodes.push(<p key={nodes.length} style={{ margin:"4px 0", lineHeight:1.6 }}>{line}</p>);
    }
  }
  flushBullets();
  return <div>{nodes}</div>;
}

// ─── Earnings Panel ──────────────────────────────────────────────

function EarningsPanel({ symbol }) {
  const [filings,     setFilings]     = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);
  const [selAcc,      setSelAcc]      = useState(null);
  const [summaries,   setSummaries]   = useState({});
  const [summLoading, setSummLoading] = useState(false);
  const [expanded,    setExpanded]    = useState(true);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setLoading(true);
    setFilings(null);
    setError(null);
    setSelAcc(null);
    setSummaries({});

    fetch(`${API}/api/earnings/${symbol}`)
      .then(r => r.json())
      .then(d => {
        if (cancelled) return;
        if (d.detail) setError(d.detail);
        else setFilings(d);
      })
      .catch(e => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [symbol]);

  const loadSummary = useCallback(async (acc) => {
    if (selAcc === acc) { setSelAcc(null); return; }
    setSelAcc(acc);
    setExpanded(true);
    if (summaries[acc]) return;
    setSummLoading(true);
    try {
      const r = await fetch(`${API}/api/earnings/${symbol}/summary/${encodeURIComponent(acc)}`);
      const d = await r.json();
      setSummaries(prev => ({ ...prev, [acc]: d.summary || d.detail || "No summary available." }));
    } catch (e) {
      setSummaries(prev => ({ ...prev, [acc]: "Error loading summary." }));
    } finally {
      setSummLoading(false);
    }
  }, [symbol, summaries, selAcc]);

  if (!symbol) return (
    <div style={{ display:"grid", placeItems:"center", flex:1,
      color:"var(--ts-muted)", fontSize:12 }}>
      Select a tweet to load earnings.
    </div>
  );

  if (loading) return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"center",
      flex:1, color:"var(--ts-muted)", padding:24 }}>
      <span style={{ fontFamily:"var(--ts-mono)", fontSize:11, letterSpacing:"0.08em" }}>
        FETCHING SEC FILINGS…
      </span>
    </div>
  );

  if (error) return (
    <div style={{ display:"grid", placeItems:"center", flex:1 }}>
      <div style={{ textAlign:"center", padding:24, maxWidth:260 }}>
        <div style={{ fontFamily:"var(--ts-mono)", fontSize:10, color:"var(--ts-down)",
          letterSpacing:"0.08em", marginBottom:8 }}>UNAVAILABLE</div>
        <div style={{ fontSize:12, color:"var(--ts-muted)", lineHeight:1.55 }}>{error}</div>
      </div>
    </div>
  );

  if (!filings) return null;

  const selectedFiling = selAcc ? (filings.filings || []).find(f => f.accession === selAcc) : null;
  const selectedSumm   = selAcc ? summaries[selAcc] : null;

  return (
    <div className="ts-earn">
      <div style={{ padding:"12px 14px 10px", borderBottom:"1px solid var(--ts-border)" }}>
        <div style={{ fontFamily:"var(--ts-mono)", fontSize:9, color:"var(--ts-muted)",
          letterSpacing:"0.08em", marginBottom:8 }}>
          CLICK A FILING FOR AI ANALYSIS
        </div>
        <div className="ts-earn-filings">
          {(filings.filings || []).map((f, i) => (
            <button key={i}
              className={`ts-earn-filing-chip ${f.form === "10-K" ? "k" : "q"}${selAcc === f.accession ? " active" : ""}`}
              onClick={() => loadSummary(f.accession)}>
              {f.form} · {f.date}
            </button>
          ))}
        </div>
      </div>

      {selAcc && (
        <div className="ts-earn-summary-wrap">
          {summLoading && !selectedSumm ? (
            <div style={{ padding:"18px 14px", color:"var(--ts-muted)", fontSize:11,
              fontFamily:"var(--ts-mono)", letterSpacing:"0.06em" }}>
              GENERATING ANALYSIS… (10–20 s)
            </div>
          ) : selectedSumm ? (
            <>
              <div style={{ padding:"10px 14px 4px", fontFamily:"var(--ts-mono)", fontSize:9,
                color:"var(--ts-accent)", letterSpacing:"0.08em" }}>
                {selectedFiling?.form} · {selectedFiling?.date}
              </div>
              <div className={`ts-earn-summary${expanded ? "" : " collapsed"}`}>
                <EarningsMd text={selectedSumm} />
              </div>
              <div style={{ padding:"0 14px 14px" }}>
                <button className="ts-earn-toggle" onClick={() => setExpanded(e => !e)}>
                  {expanded ? "▲  COLLAPSE" : "▼  EXPAND"}
                </button>
              </div>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}

// ─── Sector Watchlist ─────────────────────────────────────────────

function SectorWatchlist() {
  const [quotes,  setQuotes]  = useState({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const results = await Promise.all(
      SECTORS.map(s => fetch(`${API}/api/quote/${s.ticker}`).then(r => r.json()).catch(() => null))
    );
    const map = {};
    SECTORS.forEach((s, i) => { if (results[i] && !results[i].error) map[s.ticker] = results[i]; });
    setQuotes(map);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div className="ts-sector">
      <div className="ts-sector-header">
        <span>S&amp;P SECTORS</span>
        <button className="ts-sector-refresh" onClick={load} title="Refresh">↻</button>
      </div>
      {loading ? (
        <div className="ts-sector-loading">Loading…</div>
      ) : (
        <table className="ts-sector-table">
          <thead>
            <tr>
              <th>Sector</th>
              <th>ETF</th>
              <th style={{ textAlign:"right" }}>Price</th>
              <th style={{ textAlign:"right" }}>Chg%</th>
            </tr>
          </thead>
          <tbody>
            {SECTORS.map(s => {
              const q   = quotes[s.ticker];
              const up  = (q?.change_pct ?? 0) >= 0;
              const clr = q ? (up ? "var(--ts-up)" : "var(--ts-down)") : "var(--ts-muted)";
              return (
                <tr key={s.ticker}>
                  <td className="ts-sector-name">{s.name}</td>
                  <td className="ts-sector-ticker">{s.ticker}</td>
                  <td className="ts-sector-price">{q ? fmtPrice(q.price) : "—"}</td>
                  <td className="ts-sector-chg" style={{ color: clr }}>
                    {q?.change_pct != null ? `${up ? "+" : ""}${q.change_pct.toFixed(2)}%` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── Right Panel ──────────────────────────────────────────────────

function RightPanel({ aiData, aiLoading, activeSymbol, aiEnabled }) {
  return (
    <div className="ts-right">
      <div className="ts-right-scroll">
        {aiEnabled && <AIPanel data={aiData} loading={aiLoading} symbol={activeSymbol} />}
        <SectorWatchlist />
      </div>
    </div>
  );
}

// ─── Sentiment Gauge ──────────────────────────────────────────────

function SentimentGauge({ value = 0.5 }) {
  const pct   = Math.round(value * 100);
  const label = value >= 0.65 ? "BULLISH" : value <= 0.35 ? "BEARISH" : "NEUTRAL";
  const color = value >= 0.65 ? "var(--ts-up)" : value <= 0.35 ? "var(--ts-down)" : "var(--ts-warn)";
  const r = 34, cx = 48, cy = 40;
  const fillAngle = Math.PI * (1 - value);
  const fx = cx + r * Math.cos(fillAngle);
  const fy = cy - r * Math.sin(fillAngle);
  const needleAngle = fillAngle;
  const nx = cx + r * Math.cos(needleAngle);
  const ny = cy - r * Math.sin(needleAngle);
  const largeArc = value > 0.5 ? 1 : 0;
  return (
    <div style={{ padding:"10px 14px 6px", borderBottom:"1px solid var(--ts-border)",
      display:"flex", alignItems:"center", gap:14 }}>
      <svg width={96} height={48} viewBox="0 0 96 48" style={{ flexShrink:0 }}>
        <path d={`M ${cx-r} ${cy} A ${r} ${r} 0 0 1 ${cx+r} ${cy}`}
          fill="none" stroke="var(--ts-surface)" strokeWidth={7} strokeLinecap="round" />
        <path d={`M ${cx-r} ${cy} A ${r} ${r} 0 ${largeArc} 1 ${fx} ${fy}`}
          fill="none" stroke={color} strokeWidth={7} strokeLinecap="round" />
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={color} strokeWidth={2} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={3.5} fill={color} />
      </svg>
      <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
        <span style={{ fontFamily:"var(--ts-mono)", fontSize:24, fontWeight:700, color, lineHeight:1 }}>{pct}</span>
        <span style={{ fontFamily:"var(--ts-mono)", fontSize:9, fontWeight:700, letterSpacing:"0.1em", color }}>{label}</span>
      </div>
    </div>
  );
}

// ─── AI sub-components ────────────────────────────────────────────

function ThemeList({ themes }) {
  if (!themes.length) return <div style={{ color:"var(--ts-muted)", fontSize:12 }}>No themes available.</div>;
  return (
    <div className="ts-ai-themes">
      {themes.map((t, i) => {
        const color = t.type === "positive" ? "var(--ts-up)" : t.type === "negative" ? "var(--ts-down)" : "var(--ts-warn)";
        return (
          <div key={i}>
            <div className="ts-theme-row">
              <span className="ts-theme-label">{t.label}</span>
              <span className="ts-theme-pct" style={{ color }}>{Math.round((t.weight ?? 0) * 100)}%</span>
            </div>
            <div className="ts-theme-track">
              <div className="ts-theme-fill" style={{ width:`${(t.weight??0)*100}%`, background:color }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SignalList({ signals }) {
  if (!signals.length) return <div style={{ color:"var(--ts-muted)", fontSize:12 }}>No signals available.</div>;
  return (
    <div className="ts-ai-signals">
      {signals.map((s, i) => (
        <div key={i} className={`ts-signal ${s.strength || "weak"}`}>
          <span className="ts-signal-strength">{(s.strength || "WEAK").toUpperCase()}</span>
          <span className="ts-signal-text">{s.text}</span>
        </div>
      ))}
    </div>
  );
}

function RiskList({ risks }) {
  if (!risks.length) return <div style={{ color:"var(--ts-muted)", fontSize:12 }}>No risks identified.</div>;
  return (
    <div className="ts-ai-risks">
      {risks.map((r, i) => (
        <div key={i} className="ts-risk">
          <span className="ts-risk-marker">{i + 1}</span>
          <span>{r}</span>
        </div>
      ))}
    </div>
  );
}

function AIPanel({ data, loading, symbol }) {
  const [tab, setTab] = useState("themes");
  const tldrShown = useTypewriter(data?.tldr || "", 15);
  let tldrContent;
  if (loading && !data) {
    tldrContent = <span style={{ color:"var(--ts-muted)" }}>Analysing…<span className="ts-cursor">|</span></span>;
  } else if (data?.tldr) {
    tldrContent = <>{tldrShown}{tldrShown.length < (data.tldr?.length ?? 0) && <span className="ts-cursor">|</span>}</>;
  } else {
    tldrContent = <span style={{ color:"var(--ts-muted)" }}>Select a tweet to begin analysis.</span>;
  }
  return (
    <div className="ts-ai">
      <div className="ts-ai-header">
        <div className="ts-ai-title-row">
          <span className="ts-ai-glyph">◆</span>
          <span className="ts-ai-title">AI INTELLIGENCE</span>
        </div>
        {symbol && (
          <span className="ts-mono" style={{ fontSize:10, color:"var(--ts-accent)",
            background:"oklch(0.78 0.14 75 / 0.1)", padding:"2px 7px", borderRadius:3 }}>
            ${symbol}
          </span>
        )}
      </div>
      <div className="ts-ai-tldr">
        <div className="ts-ai-tldr-label">TL;DR</div>
        <div className="ts-ai-tldr-text">{tldrContent}</div>
      </div>
      {data?.news_summary && (
        <div className="ts-ai-tldr" style={{ borderTop:"1px solid var(--ts-border)" }}>
          <div className="ts-ai-tldr-label" style={{ color:"var(--ts-blue)" }}>NEWS</div>
          <div className="ts-ai-tldr-text">{data.news_summary}</div>
        </div>
      )}
      {data && <SentimentGauge value={data.sentiment ?? 0.5} />}
      {data?.related?.length > 0 && (
        <div style={{ padding:"8px 14px", borderBottom:"1px solid var(--ts-border)" }}>
          <div className="ts-ai-related-label">RELATED TICKERS</div>
          <div className="ts-ai-related-chips">
            {data.related.map(tk => <span key={tk} className="ts-related-chip">${tk}</span>)}
          </div>
        </div>
      )}
      {data && (
        <>
          <div className="ts-ai-tabs">
            {[
              {key:"themes",  label:"Themes",  count:data.themes?.length},
              {key:"signals", label:"Signals", count:data.signals?.length},
              {key:"risks",   label:"Risks",   count:data.risks?.length},
            ].map(({key,label,count}) => (
              <button key={key} className={`ts-ai-tab${tab===key?" active":""}`} onClick={() => setTab(key)}>
                {label}{count ? ` (${count})` : ""}
              </button>
            ))}
          </div>
          <div className="ts-ai-body">
            {tab === "themes"  && <ThemeList  themes={data.themes   || []} />}
            {tab === "signals" && <SignalList signals={data.signals || []} />}
            {tab === "risks"   && <RiskList   risks={data.risks     || []} />}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Analyst Panel ───────────────────────────────────────────────

function fmtFY(dateStr) {
  if (!dateStr) return "";
  const yr = new Date(dateStr).getFullYear();
  return isNaN(yr) ? dateStr.slice(0, 4) : "FY'" + String(yr).slice(2);
}

function ratingColor(r) {
  if (!r) return "var(--ts-muted)";
  const u = r.toUpperCase();
  if (u.startsWith("A")) return "var(--ts-up)";
  if (u.startsWith("B")) return "var(--ts-accent)";
  if (u.startsWith("C")) return "var(--ts-warn)";
  return "var(--ts-down)";
}

function AnalystPanel({ symbol, currentPrice }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setLoading(true);
    setData(null);
    setError(null);

    fetch(`${API}/api/analyst/${symbol}`)
      .then(r => r.json())
      .then(d => { if (!cancelled) { if (d.detail) setError(d.detail); else setData(d); } })
      .catch(e => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [symbol]);

  if (loading) return (
    <div className="ts-analyst">
      <div style={{ padding:"20px 16px", color:"var(--ts-muted)", fontFamily:"var(--ts-mono)", fontSize:11 }}>
        Loading analyst data…
      </div>
    </div>
  );
  if (error) return (
    <div className="ts-analyst">
      <div style={{ padding:"20px 16px", color:"var(--ts-down)", fontFamily:"var(--ts-mono)", fontSize:11 }}>{error}</div>
    </div>
  );
  if (!data) return null;

  // FMP field names
  const ptc     = data.price_target_consensus || {};  // targetConsensus, targetLow, targetHigh, targetMedian
  const pts     = data.price_target_summary   || {};  // lastMonthCount, lastQuarterAvgPriceTarget, etc.
  const snap    = data.rating_snapshot        || {};  // rating, overallScore, ...
  const grades  = data.grades                 || [];  // gradingCompany, action, previousGrade, newGrade, date
  const estimates = data.estimates            || [];  // epsAvg, revenueAvg, numAnalystsEps, date

  const consensusTgt = ptc.targetConsensus ?? null;
  const medianTgt    = ptc.targetMedian    ?? null;
  const lowTgt       = ptc.targetLow       ?? null;
  const highTgt      = ptc.targetHigh      ?? null;
  const upside = consensusTgt && currentPrice
    ? ((consensusTgt - currentPrice) / currentPrice) * 100 : null;

  const barPct = (val) => {
    if (lowTgt == null || highTgt == null || lowTgt === highTgt) return 50;
    return Math.min(100, Math.max(0, ((val - lowTgt) / (highTgt - lowTgt)) * 100));
  };

  const gradeClass = (raw) => {
    const a = (raw || "").toLowerCase();
    if (a === "upgrade")                  return "upgrade";
    if (a === "downgrade")                return "downgrade";
    if (a === "initiated" || a === "init") return "initiated";
    if (a === "maintain")                 return "maintain";
    return "reiterated";
  };

  const scoreColor = (v) => {
    if (v >= 5) return "var(--ts-up)";
    if (v >= 4) return "oklch(0.55 0.17 145)";
    if (v >= 3) return "var(--ts-warn)";
    if (v >= 2) return "oklch(0.56 0.19 40)";
    return "var(--ts-down)";
  };

  const SCORES = [
    { key: "discountedCashFlowScore", label: "DCF"  },
    { key: "returnOnEquityScore",     label: "ROE"  },
    { key: "returnOnAssetsScore",     label: "ROA"  },
    { key: "debtToEquityScore",       label: "D/E"  },
    { key: "priceToEarningsScore",    label: "P/E"  },
    { key: "priceToBookScore",        label: "P/B"  },
  ];

  const hasData = consensusTgt || grades.length || estimates.length;

  return (
    <div className="ts-analyst">

      {/* ── Rating Snapshot ── */}
      {snap.rating && (
        <div className="ts-analyst-section">
          <div className="ts-analyst-title">FMP Quantitative Rating</div>
          <div style={{ display:"flex", alignItems:"center", gap:16, marginBottom: SCORES.some(s => snap[s.key] != null) ? 0 : 0 }}>
            <div style={{ textAlign:"center", minWidth:52 }}>
              <div style={{ fontFamily:"var(--ts-mono)", fontSize:32, fontWeight:700, lineHeight:1, color: ratingColor(snap.rating) }}>
                {snap.rating}
              </div>
              <div style={{ fontFamily:"var(--ts-mono)", fontSize:9, color:"var(--ts-muted)", marginTop:3 }}>
                SCORE {snap.overallScore ?? "—"}/5
              </div>
            </div>
            {pts.lastQuarterAvgPriceTarget && (
              <div style={{ flex:1 }}>
                <div className="ts-pt-summary" style={{ gridTemplateColumns:"repeat(2,1fr)" }}>
                  <div className="ts-pt-card">
                    <div className="ts-pt-card-label">1Q Avg Target</div>
                    <div className="ts-pt-card-value">{fmtPrice(pts.lastQuarterAvgPriceTarget)}</div>
                    <div style={{ fontFamily:"var(--ts-mono)", fontSize:9, color:"var(--ts-dim)", marginTop:2 }}>{pts.lastQuarterCount} analysts</div>
                  </div>
                  {pts.lastYearAvgPriceTarget && (
                    <div className="ts-pt-card">
                      <div className="ts-pt-card-label">1Y Avg Target</div>
                      <div className="ts-pt-card-value">{fmtPrice(pts.lastYearAvgPriceTarget)}</div>
                      <div style={{ fontFamily:"var(--ts-mono)", fontSize:9, color:"var(--ts-dim)", marginTop:2 }}>{pts.lastYearCount} analysts</div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          {SCORES.some(s => snap[s.key] != null) && (
            <div className="ts-score-grid">
              {SCORES.map(({ key, label }) => {
                const v = snap[key];
                if (v == null) return null;
                const col = scoreColor(v);
                return (
                  <div key={key} className="ts-score-item">
                    <div className="ts-score-header">
                      <span className="ts-score-label">{label}</span>
                      <span className="ts-score-val" style={{ color: col }}>{v}/5</span>
                    </div>
                    <div className="ts-score-track">
                      <div className="ts-score-fill" style={{ width: (v / 5 * 100) + "%", background: col }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Price Target Consensus Bar ── */}
      {consensusTgt != null && (
        <div className="ts-analyst-section">
          <div className="ts-analyst-title">Price Target Consensus</div>
          <div className="ts-pt-summary">
            <div className="ts-pt-card">
              <div className="ts-pt-card-label">Consensus</div>
              <div className="ts-pt-card-value">{fmtPrice(consensusTgt)}</div>
            </div>
            <div className="ts-pt-card">
              <div className="ts-pt-card-label">Upside</div>
              <div className={`ts-pt-card-value ${upside >= 0 ? "up" : "down"}`}>
                {upside != null ? fmtPct(upside) : "—"}
              </div>
            </div>
            <div className="ts-pt-card">
              <div className="ts-pt-card-label">Median</div>
              <div className="ts-pt-card-value">{fmtPrice(medianTgt)}</div>
            </div>
          </div>
          <div className="ts-pt-bar-wrap">
            <div className="ts-pt-bar-track">
              <div className="ts-pt-bar-fill" />
              <div className="ts-pt-marker mean" style={{ left: barPct(consensusTgt) + "%" }}
                title={`Consensus: ${fmtPrice(consensusTgt)}`} />
              {currentPrice != null && (
                <div className="ts-pt-marker current" style={{ left: barPct(currentPrice) + "%" }}
                  title={`Current: ${fmtPrice(currentPrice)}`} />
              )}
            </div>
          </div>
          <div className="ts-pt-bar-labels">
            <span>Low {fmtPrice(lowTgt)}</span>
            {currentPrice != null && <span style={{ color:"var(--ts-fg)" }}>● {fmtPrice(currentPrice)}</span>}
            <span>High {fmtPrice(highTgt)}</span>
          </div>
        </div>
      )}

      {/* ── Analyst Grades ── */}
      {grades.length > 0 && (
        <div className="ts-analyst-section">
          <div className="ts-analyst-title">Recent Grades</div>
          {grades.slice(0, 10).map((g, i) => (
            <div key={i} className="ts-rating-row">
              <span className={`ts-rating-action ${gradeClass(g.action)}`}>{g.action || "maintain"}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="ts-rating-firm">{g.gradingCompany}</div>
                <div className="ts-rating-grade">
                  {g.previousGrade && g.newGrade && g.previousGrade !== g.newGrade
                    ? `${g.previousGrade} → ${g.newGrade}`
                    : (g.newGrade || g.previousGrade || "")}
                </div>
              </div>
              <div className="ts-rating-meta">
                <span>{fmtDate(g.date)}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Annual EPS & Revenue Estimates ── */}
      {estimates.length > 0 && (
        <div className="ts-analyst-section">
          <div className="ts-analyst-title">Annual Consensus Estimates</div>
          <table className="ts-est-table">
            <thead>
              <tr>
                <th>Year</th>
                <th>EPS (Low–High)</th>
                <th>Revenue Avg</th>
                <th style={{ textAlign:"right" }}># Est</th>
              </tr>
            </thead>
            <tbody>
              {estimates.slice(0, 6).map((e, i) => {
                const epsAvg = e.epsAvg != null ? Number(e.epsAvg).toFixed(2) : null;
                const epsLow = e.epsLow != null ? Number(e.epsLow).toFixed(2) : null;
                const epsHigh = e.epsHigh != null ? Number(e.epsHigh).toFixed(2) : null;
                const epsRange = epsLow && epsHigh ? `$${epsLow} – $${epsHigh}` : epsAvg ? `$${epsAvg}` : "—";
                return (
                  <tr key={i}>
                    <td><span className="ts-est-period">{fmtFY(e.date)}</span></td>
                    <td>
                      <div style={{ fontFamily:"var(--ts-mono)", fontSize:10.5 }}>
                        {epsAvg ? <span style={{ fontWeight:700 }}>${epsAvg}</span> : "—"}
                      </div>
                      {epsLow && epsHigh && (
                        <div style={{ fontFamily:"var(--ts-mono)", fontSize:9, color:"var(--ts-dim)" }}>
                          {epsLow} – {epsHigh}
                        </div>
                      )}
                    </td>
                    <td>{e.revenueAvg != null ? fmtNum(e.revenueAvg) : "—"}</td>
                    <td><span className="ts-est-analysts">{e.numAnalystsEps ?? "—"}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!hasData && (
        <div style={{ padding:"24px 16px", color:"var(--ts-muted)", fontFamily:"var(--ts-mono)", fontSize:11, textAlign:"center" }}>
          No analyst coverage found for {symbol}.
        </div>
      )}
    </div>
  );
}

// ─── News Rail ────────────────────────────────────────────────────

function NewsRail({ articles }) {
  return (
    <div className="ts-news">
      <div className="ts-news-header">
        <span>NEWS</span>
        {articles.length > 0 && <span className="ts-news-count">{articles.length}</span>}
      </div>
      {!articles.length ? (
        <div style={{ color:"var(--ts-muted)", fontSize:12, textAlign:"center", padding:"20px 0" }}>
          Select a tweet to load news.
        </div>
      ) : (
        <div className="ts-news-list">
          {articles.map((a, i) => (
            <a key={i} href={a.link || "#"} target="_blank" rel="noopener noreferrer"
              style={{ textDecoration:"none" }}>
              <div className="ts-news-card">
                <div className="ts-news-meta">
                  <span className="ts-news-source">{a.publisher || "News"}</span>
                  <span className="ts-news-time">{fmtDate(a.published)}</span>
                  <span className="ts-news-dot" style={{ background:"var(--ts-accent)" }} />
                </div>
                <div className="ts-news-headline">{a.title}</div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── App Root ─────────────────────────────────────────────────────

function App() {
  const [tweets,       setTweets]       = useState([]);
  const [feedLoading,  setFeedLoading]  = useState(true);
  const [activeTweet,  setActiveTweet]  = useState(null);
  const [activeSymbol, setActiveSymbol] = useState(null);
  const [quote,        setQuote]        = useState(null);
  const [news,         setNews]         = useState([]);
  const [earningsInfo, setEarningsInfo] = useState(null);
  const [aiData,       setAiData]       = useState(null);
  const [aiLoading,    setAiLoading]    = useState(false);
  const [aiEnabled,    setAiEnabled]    = useState(false);
  const [fundamentals, setFundamentals] = useState(null);
  const [fundLoading,  setFundLoading]  = useState(false);
  const [timespan,     setTimespan]     = useState("day");
  const [detailView,   setDetailView]   = useState("chart");
  const [search,         setSearch]         = useState("");
  const [pendingTweets,  setPendingTweets]  = useState([]);
  const [lastRefreshed,  setLastRefreshed]  = useState(null);

  const fetchFeed = useCallback((initial = false) => {
    return fetch(`${API}/api/feed?limit=300`)
      .then(r => r.json())
      .then(d => {
        const incoming = d.tweets || [];
        if (initial) {
          setTweets(incoming);
          setFeedLoading(false);
        } else {
          setTweets(current => {
            const knownIds = new Set(current.map(t => t.id));
            const fresh = incoming.filter(t => !knownIds.has(t.id));
            if (fresh.length > 0) setPendingTweets(fresh);
            return current;
          });
        }
        setLastRefreshed(new Date());
      })
      .catch(() => { if (initial) setFeedLoading(false); });
  }, []);

  useEffect(() => { fetchFeed(true); }, [fetchFeed]);

  useEffect(() => {
    fetch(`${API}/api/config`).then(r => r.json())
      .then(c => setAiEnabled(c.ai_enabled === true))
      .catch(() => setAiEnabled(false));
  }, []);

  useEffect(() => {
    const timer = setInterval(() => fetchFeed(false), 30 * 60 * 1000);
    return () => clearInterval(timer);
  }, [fetchFeed]);

  const loadPending = useCallback(() => {
    setTweets(t => [...pendingTweets, ...t]);
    setPendingTweets([]);
  }, [pendingTweets]);

  const selectTweet = useCallback(async (tweet, symbol) => {
    const sym = (symbol || tweet.tickers?.[0] || "").toUpperCase();
    setActiveTweet(tweet);
    setQuote(null);
    setNews([]);
    setEarningsInfo(null);
    setAiData(null);
    setFundamentals(null);
    if (!sym) { setActiveSymbol(null); return; }

    setActiveSymbol(sym);
    setAiLoading(true);
    setFundLoading(true);

    // Fire quote, news, fundamentals, and earnings date in parallel
    const [qRes, nRes, fRes, eRes] = await Promise.all([
      fetch(`${API}/api/quote/${sym}`).then(r => r.json()).catch(() => null),
      fetch(`${API}/api/news/${sym}`).then(r => r.json()).catch(() => ({ news: [] })),
      fetch(`${API}/api/fundamentals/${sym}`).then(r => r.json()).catch(() => null),
      fetch(`${API}/api/earnings-date/${sym}`).then(r => r.json()).catch(() => null),
    ]);
    setQuote(qRes);
    setNews(nRes?.news || []);
    setFundamentals(fRes);
    setEarningsInfo(eRes);
    setFundLoading(false);

    // AI call — only if enabled
    if (aiEnabled) {
      try {
        const headlines = (nRes?.news || []).map(n => n.title).filter(Boolean);
        const aiRes = await fetch(`${API}/api/action-item`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tweet: tweet.text, symbol: sym,
            price:      qRes?.price      ?? 0,
            change_pct: qRes?.change_pct ?? 0,
            headlines,
          }),
        });
        setAiData(await aiRes.json());
      } catch (e) {
        console.error("AI fetch failed:", e);
      } finally {
        setAiLoading(false);
      }
    } else {
      setAiLoading(false);
    }
  }, []);

  const filtered = tweets.filter(t => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      t.text.toLowerCase().includes(q) ||
      t.tickers?.some(tk => tk.toLowerCase().includes(q))
    );
  });

  return (
    <div className="ts-shell">
      <TopBar count={tweets.length} />
      <div className="ts-main">
        <TweetFeed tweets={filtered} activeId={activeTweet?.id} onSelect={selectTweet}
          loading={feedLoading} search={search} onSearch={setSearch}
          pendingCount={pendingTweets.length} onLoadPending={loadPending}
          lastRefreshed={lastRefreshed} />
        <DetailPanel symbol={activeSymbol} quote={quote}
          timespan={timespan} onTimespanChange={setTimespan}
          detailView={detailView} onDetailViewChange={setDetailView}
          fundamentals={fundamentals} fundLoading={fundLoading}
          news={news} earningsInfo={earningsInfo} />
        <RightPanel aiData={aiData} aiLoading={aiLoading}
          activeSymbol={activeSymbol} aiEnabled={aiEnabled} />
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
