import math
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import yfinance as yf


# =========================
# Indian Market Scanner
# Swing vs Intraday Toggle
# =========================

CAPITAL_INR = 1_000_000
RISK_PER_TRADE = 0.01
MAX_ALLOCATION = 0.20
RR_TARGET = 2.5
TOP_N = 3

OUTPUT_HTML = "index.html"
PERFORMANCE_LOG = "performance_log.csv"

BENCHMARK = "^NSEI"
BENCHMARK_FALLBACKS = ["^NSEI", "NIFTYBEES.NS"]

# NIFTY / liquid large-cap universe.
# Yahoo Finance uses ".NS" suffix for NSE cash-market symbols.
UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "BHARTIARTL.NS", "ITC.NS", "LT.NS", "SBIN.NS", "AXISBANK.NS",
    "KOTAKBANK.NS", "HINDUNILVR.NS", "BAJFINANCE.NS", "ASIANPAINT.NS",
    "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS",
    "HCLTECH.NS", "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "COALINDIA.NS",
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "ADANIENT.NS",
    "ADANIPORTS.NS", "GRASIM.NS", "M&M.NS", "TATAMOTORS.NS",
    "BAJAJ-AUTO.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "DRREDDY.NS",
    "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "BRITANNIA.NS",
    "NESTLEIND.NS", "TATACONSUM.NS", "TECHM.NS", "LTIM.NS",
    "INDUSINDBK.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS", "SBILIFE.NS",
    "BPCL.NS", "IOC.NS", "HDFCAMC.NS", "DMART.NS", "PIDILITIND.NS",
    "TRENT.NS", "ABB.NS", "SIEMENS.NS", "BEL.NS", "HAL.NS",
    "DLF.NS", "IRCTC.NS", "VBL.NS", "ZOMATO.NS", "PAYTM.NS",
]

SCAN_MODES = {
    "swing": {
        "label": "Swing",
        "description": "Daily Candle",
        "period": "6mo",
        "interval": "1d",
        "benchmark_name": "NIFTY",
        "min_rows": 80,
    },
    "intraday": {
        "label": "Intraday",
        "description": "15-Min Candle",
        "period": "5d",
        "interval": "15m",
        "benchmark_name": "NIFTY",
        "min_rows": 60,
    },
}


def now_ist():
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist)


def clean_symbol(ticker):
    return ticker.replace(".NS", "")


def fmt_inr(value):
    try:
        return f"₹{round(float(value), 0):,.0f}"
    except Exception:
        return "₹0"


def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def atr(df, period=14):
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def get_single_df(data, ticker):
    if data is None or data.empty:
        return pd.DataFrame()

    try:
        if isinstance(data.columns, pd.MultiIndex):
            level0 = data.columns.get_level_values(0)
            if ticker not in level0:
                return pd.DataFrame()
            df = data[ticker].copy()
        else:
            df = data.copy()

        required = ["Open", "High", "Low", "Close", "Volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return pd.DataFrame()

        df = df.dropna(subset=required, how="any")
        df = df[df["Volume"] > 0]
        return df

    except Exception:
        return pd.DataFrame()


def benchmark_bias(bench_df):
    b = bench_df.copy()
    b["EMA20"] = ema(b["Close"], 20)
    b["EMA50"] = ema(b["Close"], 50)

    close = float(b["Close"].iloc[-1])
    ema20 = float(b["EMA20"].iloc[-1])
    ema50 = float(b["EMA50"].iloc[-1])

    if len(b) >= 6:
        change_5 = ((b["Close"].iloc[-1] / b["Close"].iloc[-6]) - 1) * 100
    else:
        change_5 = 0

    if close > ema20 > ema50 and change_5 > 0:
        bias = "Bullish"
        message = "NIFTY trend is supportive. Scanner will only show BUY setups."
    elif close < ema20 < ema50 and change_5 < 0:
        bias = "Bearish"
        message = "NIFTY trend is weak. Scanner will only show SELL setups."
    else:
        bias = "Mixed"
        message = "NIFTY is mixed/constructive. Scanner will show qualified setups, but entries need stricter confirmation."

    return {
        "bias": bias,
        "message": message,
        "close": round(close, 2),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "change_5": round(float(change_5), 2),
    }


def score_ticker(df, bench_df, ticker, mode_key):
    mode = SCAN_MODES[mode_key]

    if len(df) < mode["min_rows"] or len(bench_df) < 80:
        return None

    d = df.copy()
    d["EMA20"] = ema(d["Close"], 20)
    d["EMA50"] = ema(d["Close"], 50)
    d["ATR14"] = atr(d, 14)
    d["RSI14"] = rsi(d["Close"], 14)
    d["VolAvg20"] = d["Volume"].rolling(20).mean()

    close = float(d["Close"].iloc[-1])
    ema20 = float(d["EMA20"].iloc[-1])
    ema50 = float(d["EMA50"].iloc[-1])
    atr14 = float(d["ATR14"].iloc[-1])
    rsi14 = float(d["RSI14"].iloc[-1])
    vol = float(d["Volume"].iloc[-1])
    vol_avg = float(d["VolAvg20"].iloc[-1])

    if not all(np.isfinite(x) for x in [close, ema20, ema50, atr14, rsi14, vol_avg]):
        return None

    vol_ratio = vol / vol_avg if vol_avg > 0 else np.nan
    atr_pct = (atr14 / close) * 100 if close > 0 else np.nan

    if not np.isfinite(vol_ratio) or not np.isfinite(atr_pct):
        return None

    if len(d) < 22 or len(bench_df) < 22:
        return None

    stock_lookback = ((d["Close"].iloc[-1] / d["Close"].iloc[-22]) - 1) * 100
    bench_lookback = ((bench_df["Close"].iloc[-1] / bench_df["Close"].iloc[-22]) - 1) * 100
    rs_vs_nifty = float(stock_lookback - bench_lookback)

    if not np.isfinite(rs_vs_nifty):
        return None

    uptrend = close > ema20 > ema50
    downtrend = close < ema20 < ema50

    signal = None
    score = 50
    notes = []

    if uptrend and 50 <= rsi14 <= 72:
        signal = "BUY"
        score += 18
        notes.append("Uptrend")
    elif downtrend and 28 <= rsi14 <= 50:
        signal = "SELL"
        score += 18
        notes.append("Downtrend")
    else:
        return None

    if signal == "BUY" and rs_vs_nifty > 2.0:
        score += 12
        notes.append("Strong relative strength")
    elif signal == "SELL" and rs_vs_nifty < -2.0:
        score += 12
        notes.append("Weak relative strength")
    else:
        score += 5
        notes.append("Acceptable relative strength")

    if mode_key == "swing":
        min_atr, max_atr = 1.2, 6.5
        max_trigger_distance = 2.0
        min_vol_ratio = 0.85
        rs_filter = 0.25
    else:
        min_atr, max_atr = 0.25, 4.5
        max_trigger_distance = 1.2
        min_vol_ratio = 0.75
        rs_filter = 0.10

    if min_atr <= atr_pct <= max_atr:
        score += 8
        notes.append("Tradable volatility")
    elif atr_pct > max_atr:
        score -= 8
        notes.append("High volatility")
    else:
        score -= 4
        notes.append("Low volatility")

    if vol_ratio >= 1.25:
        score += 7
        notes.append("Strong volume")
    elif vol_ratio >= min_vol_ratio:
        score += 3
        notes.append("Normal volume")
    else:
        return None

    if signal == "BUY":
        entry = max(close, float(d["High"].iloc[-1]) * 1.002)
        stop = entry - 1.35 * atr14
        target = entry + RR_TARGET * (entry - stop)
        entry_rule = "Enter only above trigger"
    else:
        entry = min(close, float(d["Low"].iloc[-1]) * 0.998)
        stop = entry + 1.35 * atr14
        target = entry - RR_TARGET * (stop - entry)
        entry_rule = "Enter only below trigger"

    risk_per_share = abs(entry - stop)
    max_risk_rupees = CAPITAL_INR * RISK_PER_TRADE
    qty_by_risk = math.floor(max_risk_rupees / risk_per_share) if risk_per_share > 0 else 0
    qty_by_allocation = math.floor((CAPITAL_INR * MAX_ALLOCATION) / entry) if entry > 0 else 0
    qty = max(0, min(qty_by_risk, qty_by_allocation))
    trade_value = qty * entry

    trigger_distance_pct = abs(entry - close) / close * 100 if close > 0 else np.nan

    if not np.isfinite(trigger_distance_pct):
        return None

    # Quality filters
    if trigger_distance_pct > max_trigger_distance:
        return None

    if signal == "BUY" and rs_vs_nifty < rs_filter:
        return None

    if signal == "SELL" and rs_vs_nifty > -rs_filter:
        return None

    if atr_pct > max_atr:
        return None

    # Thresholds calibrated to avoid excessive low-quality ideas.
    if score >= 88:
        priority = "Highest Priority"
        grade = "A"
    elif score >= 83:
        priority = "Medium Priority"
        grade = "B+"
    elif score >= 78:
        priority = "Low Priority"
        grade = "B"
    else:
        return None

    return {
        "Mode": mode["label"],
        "Priority": priority,
        "Stock": clean_symbol(ticker),
        "Signal": signal,
        "Conviction": int(score),
        "Grade": grade,
        "Close": round(close, 2),
        "Entry": round(entry, 2),
        "Stop": round(stop, 2),
        "Target": round(target, 2),
        "RR": RR_TARGET,
        "RSI": round(rsi14, 1),
        "ATR%": f"{round(atr_pct, 2)}%",
        "Vol Ratio": round(vol_ratio, 2),
        "RS vs NIFTY": round(rs_vs_nifty, 2),
        "Trigger Distance": f"{round(trigger_distance_pct, 2)}%",
        "Qty": qty,
        "Trade Value": fmt_inr(trade_value),
        "Entry Rule": entry_rule,
        "Notes": " · ".join(notes),
    }


def download_data(tickers, mode):
    """Download market data safely. Yahoo can intermittently fail for a few NSE symbols."""
    return yf.download(
        tickers=sorted(set(tickers)),
        period=mode["period"],
        interval=mode["interval"],
        auto_adjust=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )


def get_benchmark_df(data, mode):
    """
    Prefer ^NSEI for NIFTY. If Yahoo does not return intraday/index data,
    fall back to NIFTYBEES.NS as a tradable NIFTY proxy.
    """
    for symbol in BENCHMARK_FALLBACKS:
        df = get_single_df(data, symbol)
        if not df.empty and len(df) >= mode["min_rows"]:
            return df, symbol

    # Individual retry helps when bulk Yahoo download misses the index.
    for symbol in BENCHMARK_FALLBACKS:
        try:
            retry = download_data([symbol], mode)
            df = get_single_df(retry, symbol)
            if not df.empty and len(df) >= mode["min_rows"]:
                return df, symbol
        except Exception as exc:
            print(f"Benchmark retry failed for {symbol}: {exc}")

    return pd.DataFrame(), ""


def scan_mode(mode_key):
    mode = SCAN_MODES[mode_key]
    tickers = sorted(set(UNIVERSE + BENCHMARK_FALLBACKS))

    data = download_data(tickers, mode)

    bench_df, bench_symbol = get_benchmark_df(data, mode)
    if bench_df.empty:
        print(f"Warning: NIFTY benchmark data unavailable for {mode['label']} mode. Rendering empty mode instead of failing workflow.")
        market = {
            "bias": "Unavailable",
            "message": "NIFTY benchmark data could not be downloaded from Yahoo Finance for this run.",
            "close": "-",
            "ema20": "-",
            "ema50": "-",
            "change_5": "-",
        }
        return [], market

    market = benchmark_bias(bench_df)
    if bench_symbol != "^NSEI":
        market["message"] += f" Benchmark proxy used: {clean_symbol(bench_symbol)}."

    rows = []

    for ticker in sorted(set(UNIVERSE)):
        df = get_single_df(data, ticker)
        if df.empty:
            continue

        result = score_ticker(df, bench_df, ticker, mode_key)

        if not result:
            continue

        # Do not allow trades against the broad NIFTY trend.
        if market["bias"] == "Bullish" and result["Signal"] != "BUY":
    continue

if market["bias"] == "Bearish" and result["Signal"] != "SELL":
    continue

# In mixed/constructive markets, allow only qualified setups,
# but do not block everything below 90.
if market["bias"] == "Mixed" and result["Conviction"] < 78:
    continue

        rows.append(result)

    rows = sorted(rows, key=lambda x: x["Conviction"], reverse=True)
    return rows, market


def update_performance_log(all_rows_by_mode):
    log_path = Path(PERFORMANCE_LOG)
    today = now_ist().date().isoformat()

    columns = [
        "Date", "Mode", "Rank", "Stock", "Signal", "Conviction", "Entry", "Stop",
        "Target", "RR", "Status", "Result", "R", "Days", "Notes"
    ]

    if log_path.exists():
        log = pd.read_csv(log_path)
        for col in columns:
            if col not in log.columns:
                log[col] = ""
        log = log[columns]
    else:
        log = pd.DataFrame(columns=columns)

    existing = set(
        zip(
            log.get("Date", []),
            log.get("Mode", []),
            log.get("Rank", []),
            log.get("Stock", []),
        )
    )

    new_rows = []
    for mode_key, rows in all_rows_by_mode.items():
        mode_label = SCAN_MODES[mode_key]["label"]
        for rank, row in enumerate(rows[:TOP_N], start=1):
            key = (today, mode_label, rank, row["Stock"])
            if key not in existing:
                new_rows.append({
                    "Date": today,
                    "Mode": mode_label,
                    "Rank": rank,
                    "Stock": row["Stock"],
                    "Signal": row["Signal"],
                    "Conviction": row["Conviction"],
                    "Entry": row["Entry"],
                    "Stop": row["Stop"],
                    "Target": row["Target"],
                    "RR": row["RR"],
                    "Status": "Pending Trigger",
                    "Result": "",
                    "R": "",
                    "Days": 0,
                    "Notes": f"Top 3 {mode_label} scanner pick",
                })

    if new_rows:
        log = pd.concat([pd.DataFrame(new_rows), log], ignore_index=True)

    log.to_csv(log_path, index=False)
    return log.head(120)


def df_to_html(rows):
    if not rows:
        return "<p>No qualifying setups in this mode right now.</p>"

    return pd.DataFrame(rows).to_html(
        index=False,
        classes="data-table",
        escape=False,
    )


def perf_to_html(perf_log, mode_label):
    if perf_log.empty:
        return "<p>No records yet.</p>"

    df = perf_log[perf_log["Mode"] == mode_label].head(60)
    if df.empty:
        return "<p>No records yet for this mode.</p>"

    return df.to_html(index=False, classes="data-table", escape=False)


def render_cards(rows):
    cards = ""
    for r in rows[:TOP_N]:
        cards += f"""
        <div class="setup">
          <h3>{r['Stock']} — {r['Signal']}</h3>
          <p><b>{r['Priority']}</b> · Score {r['Conviction']}</p>
          <div class="grid">
            <div>Entry<br><b>{r['Entry']}</b></div>
            <div>Stop<br><b>{r['Stop']}</b></div>
            <div>Target<br><b>{r['Target']}</b></div>
            <div>Qty<br><b>{r['Qty']}</b></div>
            <div>Value<br><b>{r['Trade Value']}</b></div>
            <div>RR<br><b>{r['RR']}</b></div>
          </div>
          <p>{r['Entry Rule']} · {r['Notes']}</p>
        </div>
        """
    return cards or "<p>No top setups in this mode right now.</p>"


def render_mode_block(mode_key, rows, market, perf_log, active=False):
    mode = SCAN_MODES[mode_key]
    mode_label = mode["label"]
    total = len(rows)
    high = sum(r["Priority"] == "Highest Priority" for r in rows)
    medium = sum(r["Priority"] == "Medium Priority" for r in rows)
    low = sum(r["Priority"] == "Low Priority" for r in rows)
    best = max([r["Conviction"] for r in rows], default=0)

    active_class = "active" if active else ""

    return f"""
    <section id="{mode_key}" class="mode-panel {active_class}">
      <div class="mode-heading">
        <h2>{mode_label} Scanner</h2>
        <p>{mode['description']} · Period {mode['period']} · Interval {mode['interval']}</p>
      </div>

      <div class="stats">
        <div class="stat"><span>Total Candidates</span><b>{total}</b></div>
        <div class="stat"><span>Highest Priority</span><b>{high}</b></div>
        <div class="stat"><span>Medium Priority</span><b>{medium}</b></div>
        <div class="stat"><span>Low Priority</span><b>{low}</b></div>
        <div class="stat"><span>Best Conviction</span><b>{best}</b></div>
      </div>

      <div class="market">
        <h2>NIFTY Bias: {market['bias']}</h2>
        <p>{market['message']}</p>
        <div class="market-grid">
          <div>NIFTY Close<br><b>{market['close']}</b></div>
          <div>EMA 20<br><b>{market['ema20']}</b></div>
          <div>EMA 50<br><b>{market['ema50']}</b></div>
          <div>5-Candle Change<br><b>{market['change_5']}%</b></div>
        </div>
      </div>

      <h2>Top 3 Setups</h2>
      <div class="setup-wrap">{render_cards(rows)}</div>

      <div class="section">
        <h2>Suggested Investment Criteria</h2>
        <p>
          <b>88+</b> Highest Priority ·
          <b>83–87</b> Medium Priority ·
          <b>78–82</b> Low Priority.
          Entry should only be considered if the trigger level breaks with confirmation.
        </p>
      </div>

      <div class="section">
        <h2>Scanner Table</h2>
        {df_to_html(rows)}
      </div>

      <div class="section">
        <h2>{mode_label} Top 3 Performance Log</h2>
        <p>Latest 60 ideas for this mode are shown first.</p>
        {perf_to_html(perf_log, mode_label)}
      </div>
    </section>
    """


def render_html(all_rows_by_mode, markets_by_mode, perf_log):
    generated_at = now_ist()
    generated_time = generated_at.strftime("%d %b %Y, %I:%M:%S %p IST")
    build_id = generated_at.strftime("%Y%m%d%H%M%S")

    swing_block = render_mode_block(
        "swing",
        all_rows_by_mode["swing"],
        markets_by_mode["swing"],
        perf_log,
        active=True,
    )

    intraday_block = render_mode_block(
        "intraday",
        all_rows_by_mode["intraday"],
        markets_by_mode["intraday"],
        perf_log,
        active=False,
    )

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>Indian Market Scanner</title>
<style>
body {{
  margin: 0;
  font-family: Arial, sans-serif;
  background: #0f172a;
  color: #e5e7eb;
}}

.topbar {{
  max-width: 1150px;
  margin: 0 auto;
  padding: 18px 18px 0;
}}

.back-link {{
  color: #38bdf8;
  text-decoration: none;
  font-weight: 700;
  font-size: 14px;
}}

.back-link:hover {{
  color: #7dd3fc;
}}

.container {{
  max-width: 1150px;
  margin: 0 auto;
  padding: 24px 18px 60px;
}}

h1 {{
  font-size: 32px;
  margin: 0 0 6px;
}}

h2 {{
  font-size: 20px;
}}

.subtitle {{
  color: #94a3b8;
  margin-bottom: 18px;
  line-height: 1.5;
}}

.toggle-wrap {{
  display: flex;
  gap: 10px;
  margin: 18px 0 24px;
  flex-wrap: wrap;
}}

.toggle-btn {{
  background: #111827;
  color: #e5e7eb;
  border: 1px solid #243041;
  border-radius: 999px;
  padding: 11px 18px;
  cursor: pointer;
  font-weight: 700;
}}

.toggle-btn.active {{
  background: #38bdf8;
  color: #07111f;
  border-color: #38bdf8;
}}

.mode-panel {{
  display: none;
}}

.mode-panel.active {{
  display: block;
}}

.mode-heading {{
  background: #111827;
  border: 1px solid #243041;
  border-radius: 18px;
  padding: 18px;
  margin-bottom: 18px;
}}

.mode-heading p {{
  color: #94a3b8;
  margin-bottom: 0;
}}

.stats {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}}

.stat, .market, .setup, .section {{
  background: #111827;
  border: 1px solid #243041;
  border-radius: 18px;
  padding: 18px;
}}

.stat span {{
  display: block;
  color: #94a3b8;
  font-size: 13px;
}}

.stat b {{
  font-size: 24px;
}}

.market {{
  margin-bottom: 22px;
}}

.market-grid, .grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}}

.grid {{
  grid-template-columns: repeat(3, 1fr);
}}

.market-grid div, .grid div {{
  background: #0b1220;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 10px;
  color: #94a3b8;
}}

.market-grid b, .grid b {{
  color: #e5e7eb;
}}

.setup-wrap {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 22px;
}}

.section {{
  margin-top: 18px;
  overflow-x: auto;
}}

.data-table {{
  border-collapse: collapse;
  width: 100%;
  min-width: 1250px;
  font-size: 13px;
}}

.data-table th, .data-table td {{
  border-bottom: 1px solid #243041;
  padding: 9px;
  text-align: left;
  white-space: nowrap;
}}

.data-table th {{
  background: #0b1220;
}}

.disclaimer {{
  color: #94a3b8;
  font-size: 13px;
  line-height: 1.6;
  margin-top: 24px;
}}

@media (max-width: 800px) {{
  h1 {{
    font-size: 26px;
  }}

  .stats,
  .setup-wrap,
  .market-grid {{
    grid-template-columns: 1fr;
  }}
}}
</style>
</head>
<body>
<div class="topbar">
  <a class="back-link" href="https://pankajmanchnda.github.io/trading-agents/">
    ← Back to Trading Agents Dashboard
  </a>
</div>

<div class="container">
  <h1>Indian Market Scanner</h1>
  <div class="subtitle">
    Generated on {generated_time} · Build {build_id} · NIFTY benchmark · Swing vs Intraday scanner
  </div>

  <div class="toggle-wrap">
    <button class="toggle-btn active" onclick="showMode('swing', this)">Swing Daily Candle</button>
    <button class="toggle-btn" onclick="showMode('intraday', this)">Intraday 15-Min Candle</button>
  </div>

  {swing_block}
  {intraday_block}

  <p class="disclaimer">
    Disclaimer: This dashboard is for educational and research purposes only.
    It is not financial advice or a trade recommendation.
    Intraday prices from Yahoo Finance may be delayed depending on exchange/feed availability.
  </p>
</div>

<script>
function showMode(mode, button) {{
  document.querySelectorAll('.mode-panel').forEach(function(panel) {{
    panel.classList.remove('active');
  }});

  document.querySelectorAll('.toggle-btn').forEach(function(btn) {{
    btn.classList.remove('active');
  }});

  document.getElementById(mode).classList.add('active');
  button.classList.add('active');
}}
</script>
</body>
</html>"""

    Path(OUTPUT_HTML).write_text(html, encoding="utf-8")


def main():
    all_rows_by_mode = {}
    markets_by_mode = {}

    for mode_key in SCAN_MODES:
        rows, market = scan_mode(mode_key)
        all_rows_by_mode[mode_key] = rows
        markets_by_mode[mode_key] = market
        print(f"{SCAN_MODES[mode_key]['label']}: generated {len(rows)} candidates.")

    perf_log = update_performance_log(all_rows_by_mode)
    render_html(all_rows_by_mode, markets_by_mode, perf_log)

    print(f"Generated {OUTPUT_HTML}.")


if __name__ == "__main__":
    main()
