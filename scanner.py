import math
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import yfinance as yf


# =========================
# Indian Market Scanner
# Swing vs Intraday Toggle - Professional Risk Model
# =========================

CAPITAL_INR = 1_000_000
RISK_PER_TRADE = 0.01
MAX_ALLOCATION = 0.20
RR_TARGET = 2.0
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

    # Additional liquid F&O / high-volume names to preserve the wider opportunity set
    # used by the earlier Indian scanner.
    "ABCAPITAL.NS", "APLAPOLLO.NS", "ABBOTINDIA.NS", "CUMMINSIND.NS",
    "DIXON.NS", "POLYCAB.NS", "PERSISTENT.NS", "COFORGE.NS",
    "OFSS.NS", "MPHASIS.NS", "INDIGO.NS", "NAUKRI.NS",
    "AMBUJACEM.NS", "SHREECEM.NS", "GAIL.NS", "VEDL.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "IDFCFIRSTB.NS",
    "FEDERALBNK.NS", "AUBANK.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS",
    "LICHSGFIN.NS", "RECLTD.NS", "PFC.NS", "IRFC.NS",
    "BHEL.NS", "SAIL.NS", "NMDC.NS", "JINDALSTEL.NS",
    "TVSMOTOR.NS", "ASHOKLEY.NS", "BOSCHLTD.NS", "MOTHERSON.NS",
    "PAGEIND.NS", "COLPAL.NS", "MARICO.NS", "GODREJCP.NS",
    "BIOCON.NS", "LUPIN.NS", "AUROPHARMA.NS", "TORNTPHARM.NS",
]

# De-duplicate while preserving order.
UNIVERSE = list(dict.fromkeys(UNIVERSE))

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


def score_ticker(df, bench_df, ticker, mode_key, relaxed=False):
    mode = SCAN_MODES[mode_key]

    if len(df) < mode["min_rows"] or len(bench_df) < min(22, mode["min_rows"]):
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

    ema20_prev = float(d["EMA20"].iloc[-6]) if len(d) >= 26 and np.isfinite(d["EMA20"].iloc[-6]) else ema20
    last_high = float(d["High"].iloc[-1])
    last_low = float(d["Low"].iloc[-1])

    if mode_key == "swing":
        if relaxed:
            # Swing fallback settings.
            # Used only when the normal swing scan produces zero candidates.
            # This keeps the dashboard useful without touching Intraday logic.
            min_atr, max_atr = 0.70, 7.00
            max_trigger_distance = 3.00
            min_vol_ratio = 0.65
            min_rs = 0.00
            rsi_buy_min, rsi_buy_max = 48, 72
            rsi_sell_min, rsi_sell_max = 28, 58
            max_extension = 8.00
        else:
            # Normal swing settings: selective, but not overly restrictive.
            min_atr, max_atr = 0.90, 6.50
            max_trigger_distance = 2.25
            min_vol_ratio = 0.80
            min_rs = 0.50
            rsi_buy_min, rsi_buy_max = 50, 70
            rsi_sell_min, rsi_sell_max = 30, 54
            max_extension = 6.50
    else:
        # Intraday setups remain strict and unchanged.
        min_atr, max_atr = 0.35, 3.0
        max_trigger_distance = 0.75
        min_vol_ratio = 1.25
        min_rs = 0.75
        rsi_buy_min, rsi_buy_max = 54, 68
        rsi_sell_min, rsi_sell_max = 32, 46
        max_extension = 3.8

    if mode_key == "swing" and relaxed:
        # In fallback mode, keep market-direction discipline but relax the
        # EMA-stack requirement so weak/bearish phases can still surface
        # reasonable SELL candidates.
        buy_trend = close > ema20 and close > ema50
        sell_trend = close < ema20 and close < ema50
    else:
        buy_trend = close > ema20 > ema50 and ema20 > ema20_prev
        sell_trend = close < ema20 < ema50 and ema20 < ema20_prev

    signal = None
    score = 50
    notes = []

    if buy_trend and rsi_buy_min <= rsi14 <= rsi_buy_max and rs_vs_nifty >= min_rs:
        signal = "BUY"
        score += 16
        notes.append("Confirmed uptrend" if not relaxed else "Relaxed swing uptrend")
    elif sell_trend and rsi_sell_min <= rsi14 <= rsi_sell_max and rs_vs_nifty <= -min_rs:
        signal = "SELL"
        score += 16
        notes.append("Confirmed downtrend" if not relaxed else "Relaxed swing downtrend")
    else:
        return None

    # Structure-aware stop logic. Earlier builds used a fixed ATR stop from entry.
    # This version places the stop beyond recent market structure plus an ATR buffer,
    # which is less vulnerable to ordinary noise/whipsaws. Position size then adjusts
    # downward automatically if the stop is wider.
    if mode_key == "swing":
        if relaxed:
            stop_atr_mult = 1.35
            structure_lookback = 8
            stop_buffer_mult = 0.10
            max_risk_pct = 8.0
        else:
            stop_atr_mult = 1.45
            structure_lookback = 10
            stop_buffer_mult = 0.12
            max_risk_pct = 7.5
    else:
        stop_atr_mult = 1.25
        structure_lookback = 12
        stop_buffer_mult = 0.10
        max_risk_pct = 3.5

    recent_swing_low = float(d["Low"].tail(structure_lookback).min())
    recent_swing_high = float(d["High"].tail(structure_lookback).max())

    if signal == "BUY":
        extension_pct = ((close / ema20) - 1) * 100 if ema20 > 0 else np.nan
        if not np.isfinite(extension_pct) or extension_pct > max_extension:
            return None
        entry = max(close, last_high * 1.002)
        atr_stop = entry - stop_atr_mult * atr14
        structure_stop = recent_swing_low - stop_buffer_mult * atr14
        stop = min(atr_stop, structure_stop)
        target = entry + RR_TARGET * (entry - stop)
        entry_rule = "Enter only above trigger; prefer candle close confirmation"
    else:
        extension_pct = ((ema20 / close) - 1) * 100 if close > 0 else np.nan
        if not np.isfinite(extension_pct) or extension_pct > max_extension:
            return None
        entry = min(close, last_low * 0.998)
        atr_stop = entry + stop_atr_mult * atr14
        structure_stop = recent_swing_high + stop_buffer_mult * atr14
        stop = max(atr_stop, structure_stop)
        target = entry - RR_TARGET * (stop - entry)
        entry_rule = "Enter only below trigger; prefer candle close confirmation"

    risk_pct = abs(entry - stop) / entry * 100 if entry > 0 else np.nan
    if not np.isfinite(risk_pct) or risk_pct > max_risk_pct:
        return None

    trigger_distance_pct = abs(entry - close) / close * 100 if close > 0 else np.nan
    if not np.isfinite(trigger_distance_pct):
        return None

    # Expert quality gates: reject ideas that are too far away, too illiquid today,
    # too quiet, too volatile, or only weakly outperforming/underperforming NIFTY.
    if trigger_distance_pct > max_trigger_distance:
        return None
    if vol_ratio < min_vol_ratio:
        return None
    if not (min_atr <= atr_pct <= max_atr):
        return None

    # Incremental expert scoring. This prevents almost every passing trade from
    # becoming Highest Priority and reserves A-grade status for cleaner setups.
    if signal == "BUY":
        if rs_vs_nifty >= min_rs * 2:
            score += 12
            notes.append("Strong relative strength")
        else:
            score += 7
            notes.append("Positive relative strength")

        if 54 <= rsi14 <= 66:
            score += 7
            notes.append("RSI sweet spot")
        elif 50 <= rsi14 <= 70:
            score += 4
            notes.append("Healthy RSI")
    else:
        if rs_vs_nifty <= -min_rs * 2:
            score += 12
            notes.append("Weak relative strength")
        else:
            score += 7
            notes.append("Negative relative strength")

        if 34 <= rsi14 <= 46:
            score += 7
            notes.append("RSI sweet spot")
        elif 30 <= rsi14 <= 50:
            score += 4
            notes.append("Healthy RSI")

    if vol_ratio >= 1.35:
        score += 8
        notes.append("Institutional volume")
    elif vol_ratio >= 1.05:
        score += 5
        notes.append("Good volume")
    else:
        score += 2
        notes.append("Acceptable volume")

    if mode_key == "swing":
        if 1.2 <= atr_pct <= 4.5:
            score += 6
            notes.append("Clean swing volatility")
        else:
            score += 3
            notes.append("Acceptable volatility")
    else:
        if 0.35 <= atr_pct <= 2.8:
            score += 6
            notes.append("Clean intraday volatility")
        else:
            score += 3
            notes.append("Acceptable volatility")

    if trigger_distance_pct <= max_trigger_distance * 0.55:
        score += 5
        notes.append("Close to trigger")
    else:
        score += 2
        notes.append("Trigger needs confirmation")

    if extension_pct <= max_extension * 0.55:
        score += 5
        notes.append("Not extended")
    else:
        score += 2
        notes.append("Slightly extended")

    if relaxed:
        notes.append("Swing fallback candidate")
    notes.append("Structure-aware stop")
    risk_per_share = abs(entry - stop)
    max_risk_rupees = CAPITAL_INR * RISK_PER_TRADE
    qty_by_risk = math.floor(max_risk_rupees / risk_per_share) if risk_per_share > 0 else 0
    qty_by_allocation = math.floor((CAPITAL_INR * MAX_ALLOCATION) / entry) if entry > 0 else 0
    qty = max(0, min(qty_by_risk, qty_by_allocation))
    trade_value = qty * entry

    if qty <= 0 or trade_value <= 0:
        return None

    # Professional risk-model normalization.
    # This is a setup-quality score, NOT a win-probability score.
    # No live market setup should display 100 because no trade is loss-proof.
    # Excellent setups are intentionally capped in the low/mid-90s.
    raw_score = int(round(score))
    if raw_score >= 98:
        score = 94
    elif raw_score >= 94:
        score = 92
    elif raw_score >= 90:
        score = 90
    else:
        score = max(0, min(raw_score, 89))

    if mode_key == "swing":
        if score >= 88:
            priority = "Qualified Candidate"
            grade = "A"
        elif score >= 82:
            priority = "Qualified Candidate"
            grade = "B+"
        elif score >= 74:
            priority = "Qualified Candidate"
            grade = "B"
        else:
            return None
    else:
        if score >= 90:
            priority = "Qualified Candidate"
            grade = "A"
        elif score >= 84:
            priority = "Qualified Candidate"
            grade = "B+"
        elif score >= 78:
            priority = "Qualified Candidate"
            grade = "B"
        else:
            return None

    return {
        "Mode": mode["label"],
        "Scan Type": "Fallback" if relaxed else "Normal",
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
        "Extension": f"{round(extension_pct, 2)}%",
        "Qty": qty,
        "Trade Value": fmt_inr(trade_value),
        "Entry Rule": entry_rule,
        "Notes": " · ".join(notes),
    }


def calibrate_priorities(rows, highest_cap=5):
    """
    Assign final priority after all candidates are ranked.

    Swing and Intraday use different thresholds:
    - Swing is intentionally a little looser so daily output does not go empty too often.
    - Intraday remains stricter because it already produces daily picks.
    """
    calibrated = []

    for rank, row in enumerate(sorted(rows, key=lambda x: x["Conviction"], reverse=True), start=1):
        score = int(row["Conviction"])
        mode_label = str(row.get("Mode", "")).lower()

        if mode_label == "swing":
            high_threshold = 88
            medium_threshold = 82
            low_threshold = 74
        else:
            high_threshold = 90
            medium_threshold = 84
            low_threshold = 78

        if rank <= highest_cap and score >= high_threshold:
            row["Priority"] = "Highest Priority"
            row["Grade"] = "A"
        elif score >= medium_threshold:
            row["Priority"] = "Medium Priority"
            row["Grade"] = "B+"
        elif score >= low_threshold:
            row["Priority"] = "Low Priority"
            row["Grade"] = "B"
        else:
            continue

        calibrated.append(row)

    return calibrated

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

    def collect_candidates(relaxed=False):
        candidates = []

        for ticker in sorted(set(UNIVERSE)):
            df = get_single_df(data, ticker)
            if df.empty:
                continue

            result = score_ticker(df, bench_df, ticker, mode_key, relaxed=relaxed)

            if not result:
                continue

            # Do not allow trades against the broad NIFTY trend.
            if market["bias"] == "Bullish" and result["Signal"] != "BUY":
                continue

            if market["bias"] == "Bearish" and result["Signal"] != "SELL":
                continue

            # In a mixed NIFTY tape, demand stronger setup quality.
            if market["bias"] == "Mixed":
                required_score = 82 if mode_key == "swing" else 84
                if result["Conviction"] < required_score:
                    continue

            candidates.append(result)

        return candidates

    rows = collect_candidates(relaxed=False)

    # Swing-only fallback: if normal swing filters return zero, use a looser
    # second pass. Intraday is intentionally untouched because it already
    # generates regular picks.
    if mode_key == "swing" and len(rows) == 0:
        rows = collect_candidates(relaxed=True)
        if rows:
            market["message"] += " Normal swing scan had no candidates, so a relaxed swing fallback was used."

    rows = calibrate_priorities(rows, highest_cap=5)
    rows = rows[:20]
    return rows, market

def safe_float(value, default=np.nan):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default




def format_distance(value):
    """Format a price distance as rupees and percent, e.g. ₹12.35 / 2.41%."""
    rupees, pct = value
    if not np.isfinite(rupees) or not np.isfinite(pct):
        return ""
    sign = "+" if rupees >= 0 else "-"
    return f"{sign}₹{abs(rupees):.2f} / {sign}{abs(pct):.2f}%"


def stop_target_distance(signal, current_price, stop, target):
    """Return formatted distance from current price to stop and target.

    Values are positive while the stop/target is still away from current price.
    Negative values mean price has already moved beyond that level.
    """
    if not all(np.isfinite(x) for x in [current_price, stop, target]) or current_price <= 0:
        return "", ""

    signal = str(signal).upper().strip()
    if signal == "BUY":
        stop_rupees = current_price - stop
        target_rupees = target - current_price
    elif signal == "SELL":
        stop_rupees = stop - current_price
        target_rupees = current_price - target
    else:
        return "", ""

    stop_pct = (stop_rupees / current_price) * 100
    target_pct = (target_rupees / current_price) * 100
    return format_distance((stop_rupees, stop_pct)), format_distance((target_rupees, target_pct))

def symbol_to_yahoo(stock):
    stock = str(stock).strip()
    if stock.endswith('.NS') or stock.startswith('^'):
        return stock
    return f"{stock}.NS"


def get_log_history(stock, mode_label):
    """
    Fetch price history for performance-log tracking.

    Swing rows are checked on daily candles.
    Intraday rows are checked on 15-minute candles.
    """
    symbol = symbol_to_yahoo(stock)

    if str(mode_label).lower() == 'intraday':
        period = '15d'
        interval = '15m'
    else:
        period = '3mo'
        interval = '1d'

    try:
        data = yf.download(
            tickers=[symbol],
            period=period,
            interval=interval,
            auto_adjust=False,
            group_by='ticker',
            threads=False,
            progress=False,
        )
        return get_single_df(data, symbol)
    except Exception as exc:
        print(f"Performance-log price fetch failed for {symbol}: {exc}")
        return pd.DataFrame()


def evaluate_trade_path(row, hist):
    """
    Update one logged idea with current price and first-hit status.

    Logic is conservative and path-aware:
    - First wait for the entry trigger.
    - After the trigger, mark whether target or stop was touched first.
    - If both stop and target are touched inside the same candle, mark it ambiguous
      instead of pretending certainty.
    """
    today = now_ist().date()

    date_value = str(row.get('Date', '')).strip()
    try:
        start_date = pd.to_datetime(date_value).date()
    except Exception:
        start_date = today

    days = max(0, (today - start_date).days)

    result = {
        'Current Price': row.get('Current Price', ''),
        'Stop Away': row.get('Stop Away', ''),
        'Target Away': row.get('Target Away', ''),
        'Status': row.get('Status', 'Pending Trigger'),
        'Result': row.get('Result', ''),
        'R': row.get('R', ''),
        'Days': days,
        'First Hit': row.get('First Hit', ''),
        'Hit Date': row.get('Hit Date', ''),
    }

    if hist.empty:
        return result

    h = hist.copy()
    h = h.dropna(subset=['High', 'Low', 'Close'], how='any')
    if h.empty:
        return result

    try:
        h = h[h.index.date >= start_date]
    except Exception:
        pass

    if h.empty:
        return result

    current_price = safe_float(h['Close'].iloc[-1], np.nan)
    if np.isfinite(current_price):
        result['Current Price'] = round(current_price, 2)

    signal = str(row.get('Signal', '')).upper().strip()
    entry = safe_float(row.get('Entry'))
    stop = safe_float(row.get('Stop'))
    target = safe_float(row.get('Target'))
    rr_value = safe_float(row.get('RR'), RR_TARGET)

    if signal not in {'BUY', 'SELL'} or not all(np.isfinite(x) for x in [entry, stop, target]):
        return result

    if np.isfinite(current_price):
        stop_away, target_away = stop_target_distance(signal, current_price, stop, target)
        result['Stop Away'] = stop_away
        result['Target Away'] = target_away

    triggered = False

    for ts, candle in h.iterrows():
        high = safe_float(candle.get('High'))
        low = safe_float(candle.get('Low'))
        if not np.isfinite(high) or not np.isfinite(low):
            continue

        try:
            hit_date = ts.date().isoformat()
        except Exception:
            hit_date = str(ts)

        triggered_this_candle = False

        if signal == 'BUY':
            if not triggered:
                if high >= entry:
                    triggered = True
                    triggered_this_candle = True
                else:
                    continue

            target_hit = high >= target
            stop_hit = low <= stop

        else:  # SELL
            if not triggered:
                if low <= entry:
                    triggered = True
                    triggered_this_candle = True
                else:
                    continue

            target_hit = low <= target
            stop_hit = high >= stop

        # If entry and exit level are both touched inside the same candle,
        # the OHLC data cannot prove which happened first. Mark it ambiguous
        # instead of recording a false win/loss.
        if triggered_this_candle and (target_hit or stop_hit):
            result.update({
                'Status': 'Ambiguous Entry Candle',
                'Result': 'Ambiguous',
                'R': '',
                'First Hit': 'Entry/exit same candle',
                'Hit Date': hit_date,
            })
            return result

        if target_hit and stop_hit:
            result.update({
                'Status': 'Ambiguous Same Candle',
                'Result': 'Ambiguous',
                'R': '',
                'First Hit': 'Target and Stop same candle',
                'Hit Date': hit_date,
            })
            return result

        if target_hit:
            result.update({
                'Status': 'Target Hit First',
                'Result': 'Win',
                'R': round(rr_value, 2),
                'First Hit': 'Target',
                'Hit Date': hit_date,
            })
            return result

        if stop_hit:
            result.update({
                'Status': 'Stop Hit First',
                'Result': 'Loss',
                'R': -1,
                'First Hit': 'Stop',
                'Hit Date': hit_date,
            })
            return result

    if triggered:
        result.update({
            'Status': 'Active After Trigger',
            'Result': '',
            'R': '',
            'First Hit': '',
            'Hit Date': '',
        })
    else:
        result.update({
            'Status': 'Pending Trigger',
            'Result': '',
            'R': '',
            'First Hit': '',
            'Hit Date': '',
        })

    return result


def refresh_performance_status(log):
    """Add current price and first-hit outcome markers to the performance log.

    Keep all log columns as object dtype before assigning numeric values.
    This prevents pandas/GitHub runner dtype errors when older CSV columns
    were inferred as string columns but we later assign prices like 1828.4.
    """
    if log.empty:
        return log

    log = log.copy().astype(object)

    # Keep the runtime manageable on GitHub Actions by updating the latest 120 rows.
    rows_to_update = log.head(120).copy()
    history_cache = {}

    for idx, row in rows_to_update.iterrows():
        stock = str(row.get('Stock', '')).strip()
        mode_label = str(row.get('Mode', 'Swing')).strip() or 'Swing'
        if not stock:
            continue

        cache_key = (stock, mode_label)
        if cache_key not in history_cache:
            history_cache[cache_key] = get_log_history(stock, mode_label)

        updates = evaluate_trade_path(row, history_cache[cache_key])
        for col, value in updates.items():
            log.at[idx, col] = value

    return log


def update_performance_log(all_rows_by_mode):
    log_path = Path(PERFORMANCE_LOG)
    today = now_ist().date().isoformat()

    columns = [
        "Date", "Mode", "Rank", "Stock", "Signal", "Conviction", "Entry", "Stop",
        "Target", "RR", "Current Price", "Stop Away", "Target Away", "Status", "First Hit", "Hit Date",
        "Result", "R", "Days", "Notes"
    ]

    if log_path.exists():
        log = pd.read_csv(log_path)
        for col in columns:
            if col not in log.columns:
                log[col] = ""
        log = log[columns].astype(object)
        # Clean older over-inflated scores from previous experimental builds.
        log["Conviction"] = pd.to_numeric(log["Conviction"], errors="coerce").clip(upper=94)
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
                    "Current Price": row["Close"],
                    "Stop Away": "",
                    "Target Away": "",
                    "Status": "Pending Trigger",
                    "First Hit": "",
                    "Hit Date": "",
                    "Result": "",
                    "R": "",
                    "Days": 0,
                    "Notes": f"Top 3 {mode_label} scanner pick",
                })

    if new_rows:
        log = pd.concat([pd.DataFrame(new_rows), log], ignore_index=True)

    # Make the dataframe assignment-safe before refreshing current prices/results.
    log = log.astype(object)
    log = refresh_performance_status(log)
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
          Swing is calibrated slightly looser to avoid empty daily output:
          <b>88–94</b> Highest Priority candidate range ·
          <b>82–87</b> Medium Priority ·
          <b>74–81</b> Low Priority.
          Intraday remains stricter:
          <b>90–94</b> Highest Priority ·
          <b>84–89</b> Medium Priority ·
          <b>78–83</b> Low Priority.
          Only the top 5 ranked ideas per mode can receive the Highest Priority label. Score is setup quality, not probability of profit. No trade is assumed loss-proof, so the model intentionally avoids 100 scores. Stops use structure-aware ATR placement and targets use a more realistic 2R objective. Expert filter still requires NIFTY-direction alignment, relative strength/weakness, volume confirmation, controlled volatility, and a nearby trigger. Entry should only be considered if the trigger level breaks with confirmation.
        </p>
      </div>

      <div class="section">
        <h2>Scanner Table</h2>
        {df_to_html(rows)}
      </div>

      <div class="section">
        <h2>{mode_label} Top 3 Performance Log</h2>
        <p>Latest 60 ideas for this mode are shown first. Current Price, Stop Away, Target Away, First Hit, and Hit Date update on each scanner run to help track whether target or stop-loss was touched first.</p>
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

.refresh-panel {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 14px 0 18px 0;
  color: #94a3b8;
  font-size: 13px;
  flex-wrap: wrap;
}}

.refresh-panel button {{
  background: #111827;
  border: 1px solid #243041;
  color: #e5e7eb;
  border-radius: 999px;
  padding: 9px 15px;
  cursor: pointer;
  font-weight: 700;
}}

.refresh-panel button.active {{
  background: #38bdf8;
  color: #020617;
  border-color: #38bdf8;
}}

.refresh-note {{
  color: #64748b;
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

  <div class="refresh-panel">
    <button id="autoRefreshBtn" type="button">Auto-refresh OFF</button>
    <span id="refreshCountdown">Manual refresh mode</span>
    <span class="refresh-note">Reloads this page every 5 minutes when enabled.</span>
  </div>

  <div class="toggle-wrap">
    <button class="toggle-btn active" onclick="showMode('swing', this)">Swing Daily Candle</button>
    <button class="toggle-btn" onclick="showMode('intraday', this)">Intraday 15-Min Candle</button>
  </div>

  {swing_block}
  {intraday_block}

  <p class="disclaimer">
    Disclaimer: This dashboard is for educational and research purposes only.
    Scores are setup-quality rankings, not win probabilities. No market setup is guaranteed or loss-proof.
    This is not financial advice or a trade recommendation.
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

(function () {{
  const REFRESH_SECONDS = 300;
  const STORAGE_KEY = "indian_scanner_auto_refresh_enabled";

  const btn = document.getElementById("autoRefreshBtn");
  const countdown = document.getElementById("refreshCountdown");

  if (!btn || !countdown) return;

  let enabled = localStorage.getItem(STORAGE_KEY) === "true";
  let remaining = REFRESH_SECONDS;
  let timer = null;

  function formatTime(seconds) {{
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${{mins}}:${{String(secs).padStart(2, "0")}}`;
  }}

  function updateUi() {{
    if (enabled) {{
      btn.textContent = "Auto-refresh ON";
      btn.classList.add("active");
      countdown.textContent = `Next refresh in ${{formatTime(remaining)}}`;
    }} else {{
      btn.textContent = "Auto-refresh OFF";
      btn.classList.remove("active");
      countdown.textContent = "Manual refresh mode";
    }}
  }}

  function startTimer() {{
    if (timer) clearInterval(timer);

    timer = setInterval(function () {{
      if (!enabled) return;

      remaining -= 1;
      if (remaining <= 0) {{
        const url = new URL(window.location.href);
        url.searchParams.set("v", Date.now().toString());
        window.location.href = url.toString();
        return;
      }}

      updateUi();
    }}, 1000);
  }}

  btn.addEventListener("click", function () {{
    enabled = !enabled;
    remaining = REFRESH_SECONDS;
    localStorage.setItem(STORAGE_KEY, enabled ? "true" : "false");
    updateUi();
    startTimer();
  }});

  updateUi();
  startTimer();
}})();
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
