import pandas as pd
import yfinance as yf
from datetime import datetime
import math

# ============================================================
# USER SETTINGS
# ============================================================

TOTAL_CAPITAL = 1000000        # Example: ₹10,00,000 capital
RISK_PER_TRADE_PCT = 1.0       # Risk 1% of capital per trade
MAX_ALLOCATION_PCT = 20        # Max 20% capital allocation per trade

RISK_AMOUNT = TOTAL_CAPITAL * (RISK_PER_TRADE_PCT / 100)
MAX_ALLOCATION = TOTAL_CAPITAL * (MAX_ALLOCATION_PCT / 100)

# ============================================================
# LOAD SCANNER DATA
# ============================================================

try:
    df = pd.read_csv("scanner_output.csv")
except FileNotFoundError:
    df = pd.DataFrame()
try:
    trade_log = pd.read_csv("trade_log.csv")
except FileNotFoundError:
    trade_log = pd.DataFrame()

if not df.empty and "Conviction Score" in df.columns:
    df = df.sort_values(by="Conviction Score", ascending=False)

# ============================================================
# MARKET BIAS — NIFTY
# ============================================================

def flatten_columns(data):
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

def get_nifty_bias():
    try:
        nifty = yf.download("^NSEI", period="6mo", interval="1d", progress=False, auto_adjust=False)
        nifty = flatten_columns(nifty)

        if nifty.empty or len(nifty) < 60:
            return {
                "bias": "Unknown",
                "class": "bias-neutral",
                "text": "NIFTY data unavailable.",
                "close": "-",
                "ema20": "-",
                "ema50": "-",
                "change_5d": "-"
            }

        nifty["EMA20"] = nifty["Close"].ewm(span=20).mean()
        nifty["EMA50"] = nifty["Close"].ewm(span=50).mean()

        close = float(nifty["Close"].iloc[-1])
        ema20 = float(nifty["EMA20"].iloc[-1])
        ema50 = float(nifty["EMA50"].iloc[-1])
        close_5d = float(nifty["Close"].iloc[-6])
        change_5d = ((close - close_5d) / close_5d) * 100

        if close > ema20 > ema50:
            bias = "Bullish"
            css = "bias-bullish"
            text = "Market trend supports BUY setups. SELL setups require extra caution."
        elif close < ema20 < ema50:
            bias = "Bearish"
            css = "bias-bearish"
            text = "Market trend supports SELL setups. BUY setups require extra caution."
        else:
            bias = "Mixed"
            css = "bias-neutral"
            text = "Market is mixed. Prefer only the highest-conviction setups."

        return {
            "bias": bias,
            "class": css,
            "text": text,
            "close": round(close, 2),
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
            "change_5d": round(change_5d, 2)
        }

    except Exception:
        return {
            "bias": "Unknown",
            "class": "bias-neutral",
            "text": "Could not calculate NIFTY market bias.",
            "close": "-",
            "ema20": "-",
            "ema50": "-",
            "change_5d": "-"
        }

market = get_nifty_bias()

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_value(row, col, default="-"):
    return row[col] if col in row and pd.notna(row[col]) else default

def signal_class(signal):
    s = str(signal).upper()
    if "BUY" in s:
        return "buy"
    if "SELL" in s:
        return "sell"
    return "neutral"

def priority_info(score):
    try:
        score = float(score)
    except Exception:
        score = 0

    if score >= 85:
        return ("Highest Priority", "priority-high", "row-high")
    elif score >= 80:
        return ("Medium Priority", "priority-medium", "row-medium")
    elif score >= 75:
        return ("Low Priority", "priority-low", "row-low")
    return ("Avoid", "priority-avoid", "row-avoid")

def compact_action(signal):
    s = str(signal).upper()
    if "BUY" in s:
        return "Enter only above trigger"
    if "SELL" in s:
        return "Enter only below trigger"
    return "Wait"

def market_warning(signal):
    s = str(signal).upper()

    if market["bias"] == "Bearish" and "BUY" in s:
        return "⚠️ Market bias against BUY"
    if market["bias"] == "Bullish" and "SELL" in s:
        return "⚠️ Market bias against SELL"
    if market["bias"] == "Mixed":
        return "⚠️ Mixed market"
    return "Market aligned"

def compact_notes(row):
    signal = str(safe_value(row, "Signal", "")).upper()
    rs = safe_value(row, "Relative Strength vs NIFTY", 0)
    vol = safe_value(row, "Volume Ratio", 0)

    try:
        rs = float(rs)
    except Exception:
        rs = 0

    try:
        vol = float(vol)
    except Exception:
        vol = 0

    rs_text = "Strong RS" if abs(rs) >= 8 else "Decent RS"
    vol_text = "Strong volume" if vol >= 1.5 else "Normal volume"

    if "BUY" in signal:
        return f"Uptrend · {rs_text} · {vol_text}"
    elif "SELL" in signal:
        return f"Downtrend · {rs_text} · {vol_text}"

    return "Watch"

def calculate_position(row):
    try:
        entry = float(safe_value(row, "Entry Trigger", 0))
        stop = float(safe_value(row, "Stop Loss", 0))

        per_share_risk = abs(entry - stop)

        if per_share_risk <= 0:
            return {
                "qty": "-",
                "trade_value": "-",
                "capital_pct": "-",
                "risk_amount": "-"
            }

        qty_by_risk = math.floor(RISK_AMOUNT / per_share_risk)

        if qty_by_risk <= 0:
            return {
                "qty": "Too risky",
                "trade_value": "-",
                "capital_pct": "-",
                "risk_amount": round(RISK_AMOUNT, 0)
            }

        trade_value = qty_by_risk * entry

        if trade_value > MAX_ALLOCATION:
            qty_by_allocation = math.floor(MAX_ALLOCATION / entry)
            qty = max(qty_by_allocation, 0)
            trade_value = qty * entry
        else:
            qty = qty_by_risk

        capital_pct = (trade_value / TOTAL_CAPITAL) * 100 if TOTAL_CAPITAL > 0 else 0

        return {
            "qty": qty,
            "trade_value": round(trade_value, 0),
            "capital_pct": round(capital_pct, 1),
            "risk_amount": round(RISK_AMOUNT, 0)
        }

    except Exception:
        return {
            "qty": "-",
            "trade_value": "-",
            "capital_pct": "-",
            "risk_amount": "-"
        }

def status_class(status):
    s = str(status).upper()

    if "TARGET" in s:
        return "status-win"
    if "STOP" in s:
        return "status-loss"
    if "TRIGGERED" in s:
        return "status-triggered"
    if "PENDING" in s:
        return "status-pending"
    if "EXPIRED" in s:
        return "status-expired"
    if "GAP" in s:
        return "status-gap"

    return "status-neutral"


def build_trade_log_tabs(trade_log):
    if trade_log.empty:
        return """
        <div class="empty-card">
            No performance history yet. Run performance_tracker.py after scanner.py to start logging Top 3 picks.
        </div>
        """

    trade_log = trade_log.copy()

    if "Signal Date" in trade_log.columns:
        trade_log["Signal Date"] = trade_log["Signal Date"].astype(str)
        trade_log = trade_log.sort_values(by="Signal Date", ascending=False)

    chunks = [
        trade_log.iloc[i:i + 60]
        for i in range(0, len(trade_log), 60)
    ]

    buttons = ""
    panels = ""

    for idx, chunk in enumerate(chunks):
        tab_id = f"log-tab-{idx}"

        if idx == 0:
            label = "Latest 60"
            active_class = "active"
            display_style = "block"
        else:
            start = idx * 60 + 1
            end = idx * 60 + len(chunk)
            label = f"Trades {start}-{end}"
            active_class = ""
            display_style = "none"

        buttons += f"""
        <button class="tab-button {active_class}" onclick="showTab('{tab_id}', this)">
            {label}
        </button>
        """

        rows = ""

        for _, row in chunk.iterrows():
            status = row.get("Status", "-")

            rows += f"""
            <tr>
                <td>{row.get("Signal Date", "-")}</td>
                <td>{row.get("Rank", "-")}</td>
                <td class="stock">{row.get("Symbol", "-")}</td>
                <td><span class="badge {signal_class(row.get("Signal", ""))}">{row.get("Signal", "-")}</span></td>
                <td>{row.get("Conviction Score", "-")}</td>
                <td>{row.get("Entry Trigger", "-")}</td>
                <td>{row.get("Stop Loss", "-")}</td>
                <td>{row.get("Target", "-")}</td>
                <td>{row.get("Risk/Reward", "-")}</td>
                <td><span class="status-pill {status_class(status)}">{status}</span></td>
                <td>{row.get("Result", "-")}</td>
                <td>{row.get("R Multiple", "-")}</td>
                <td>{row.get("Days Tracked", "-")}</td>
                <td>{row.get("Notes", "-")}</td>
            </tr>
            """

        panels += f"""
        <div id="{tab_id}" class="tab-panel" style="display:{display_style};">
            <div class="table-wrap performance-table">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Rank</th>
                            <th>Stock</th>
                            <th>Signal</th>
                            <th>Conviction</th>
                            <th>Entry</th>
                            <th>Stop</th>
                            <th>Target</th>
                            <th>RR</th>
                            <th>Status</th>
                            <th>Result</th>
                            <th>R</th>
                            <th>Days</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>
        </div>
        """

    return f"""
    <div class="tabs">
        <div class="tab-buttons">
            {buttons}
        </div>
        {panels}
    </div>
    """

# ============================================================
# SUMMARY METRICS
# ============================================================

total = len(df)

if not df.empty and "Signal" in df.columns:
    buy_count = len(df[df["Signal"].astype(str).str.contains("BUY", case=False, na=False)])
    sell_count = len(df[df["Signal"].astype(str).str.contains("SELL", case=False, na=False)])
else:
    buy_count = 0
    sell_count = 0

if not df.empty and "Conviction Score" in df.columns:
    high_count = len(df[df["Conviction Score"] >= 85])
    medium_count = len(df[(df["Conviction Score"] >= 80) & (df["Conviction Score"] < 85)])
    low_count = len(df[(df["Conviction Score"] >= 75) & (df["Conviction Score"] < 80)])
    best_score = df["Conviction Score"].max()
else:
    high_count = medium_count = low_count = 0
    best_score = 0

avg_rr = df["Risk/Reward"].mean() if not df.empty and "Risk/Reward" in df.columns else 0

# ============================================================
# TOP 3 CARDS
# ============================================================

if df.empty:
    top_cards = """
    <div class="empty-card">
        No high-conviction setups today. Protecting capital is also a valid trading decision.
    </div>
    """
else:
    top_cards = ""
    top3 = df.head(3)

    for _, row in top3.iterrows():
        conviction = safe_value(row, "Conviction Score", 0)
        priority_text, priority_css, _ = priority_info(conviction)
        signal = safe_value(row, "Signal")
        pos = calculate_position(row)

        top_cards += f"""
        <div class="top-card">
            <div class="top-card-header">
                <span class="stock-name">{safe_value(row, "Symbol")}</span>
                <span class="badge {signal_class(signal)}">{signal}</span>
            </div>

            <div class="priority-line">
                <span class="priority {priority_css}">{priority_text}</span>
                <strong>Score: {conviction}</strong>
            </div>

            <div class="mini-grid">
                <div><span>Entry</span><strong>{safe_value(row, "Entry Trigger")}</strong></div>
                <div><span>Stop</span><strong>{safe_value(row, "Stop Loss")}</strong></div>
                <div><span>Target</span><strong>{safe_value(row, "Target")}</strong></div>
                <div><span>RR</span><strong>{safe_value(row, "Risk/Reward")}</strong></div>
            </div>

            <div class="position-box">
                Suggested position: <strong>{pos["qty"]} shares</strong><br>
                Approx trade value: <strong>₹{pos["trade_value"]}</strong> · Capital used: <strong>{pos["capital_pct"]}%</strong>
            </div>

            <p class="small-note">{compact_action(signal)} · {market_warning(signal)}</p>
        </div>
        """

# ============================================================
# TABLE ROWS
# ============================================================

if df.empty:
    html_rows = """
    <tr>
        <td colspan="19" class="empty">
            No high-conviction trade candidates today. No trade is also a valid decision.
        </td>
    </tr>
    """
else:
    html_rows = ""

    for _, row in df.iterrows():
        signal = safe_value(row, "Signal")
        conviction = safe_value(row, "Conviction Score", 0)
        priority_text, priority_class, row_class = priority_info(conviction)
        pos = calculate_position(row)

        html_rows += f"""
        <tr class="{row_class}">
            <td><span class="priority {priority_class}">{priority_text}</span></td>
            <td class="stock">{safe_value(row, "Symbol")}</td>
            <td><span class="badge {signal_class(signal)}">{signal}</span></td>
            <td class="score">{conviction}</td>
            <td>{safe_value(row, "Grade")}</td>
            <td>{safe_value(row, "Close")}</td>
            <td>{safe_value(row, "Entry Trigger")}</td>
            <td>{safe_value(row, "Stop Loss")}</td>
            <td>{safe_value(row, "Target")}</td>
            <td>{safe_value(row, "Risk/Reward")}</td>
            <td>{safe_value(row, "RSI")}</td>
            <td>{safe_value(row, "ATR%")}%</td>
            <td>{safe_value(row, "Volume Ratio")}</td>
            <td>{safe_value(row, "Relative Strength vs NIFTY")}</td>
            <td>{safe_value(row, "Distance to Trigger%")}%</td>
            <td>{pos["qty"]}</td>
            <td>₹{pos["trade_value"]}</td>
            <td>{compact_action(signal)}</td>
            <td>{market_warning(signal)}</td>
            <td>{compact_notes(row)}</td>
        </tr>
        """

# ============================================================
# HTML
# ============================================================
performance_log_html = build_trade_log_tabs(trade_log)
html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>High-Conviction Swing Trading Scanner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <style>
        :root {{
            --bg: #f3f4f6;
            --card: #ffffff;
            --text: #111827;
            --muted: #6b7280;
            --border: #e5e7eb;
            --dark: #0f172a;

            --green: #047857;
            --green-bg: #d1fae5;
            --green-row: #f0fdf4;

            --yellow: #a16207;
            --yellow-bg: #fef3c7;
            --yellow-row: #fffbeb;

            --orange: #c2410c;
            --orange-bg: #ffedd5;
            --orange-row: #fff7ed;

            --red: #b91c1c;
            --red-bg: #fee2e2;

            --blue: #1d4ed8;
            --blue-bg: #dbeafe;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            padding: 24px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
        }}

        .header {{
            margin-bottom: 20px;
        }}

        .header h1 {{
            font-size: 36px;
            margin: 0 0 8px;
            letter-spacing: -0.8px;
        }}

        .header p {{
            color: var(--muted);
            margin: 0;
            font-size: 15px;
        }}

        .metrics {{
            display: grid;
            grid-template-columns: repeat(6, minmax(150px, 1fr));
            gap: 14px;
            margin-bottom: 20px;
        }}

        .metric {{
            background: var(--card);
            padding: 16px;
            border-radius: 14px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06);
            border: 1px solid var(--border);
        }}

        .metric span {{
            color: var(--muted);
            font-size: 13px;
            font-weight: 600;
        }}

        .metric strong {{
            display: block;
            font-size: 25px;
            margin-top: 6px;
        }}

        .market-box {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px;
            margin-bottom: 20px;
            display: grid;
            grid-template-columns: 1.3fr 3fr;
            gap: 18px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}

        .bias-pill {{
            display: inline-block;
            padding: 8px 12px;
            border-radius: 999px;
            font-weight: 900;
            margin-bottom: 10px;
        }}

        .bias-bullish {{
            background: var(--green-bg);
            color: var(--green);
        }}

        .bias-bearish {{
            background: var(--red-bg);
            color: var(--red);
        }}

        .bias-neutral {{
            background: var(--yellow-bg);
            color: var(--yellow);
        }}

        .market-stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
        }}

        .market-stats div {{
            background: #f9fafb;
            padding: 12px;
            border-radius: 12px;
            border: 1px solid var(--border);
        }}

        .market-stats span {{
            color: var(--muted);
            font-size: 12px;
            display: block;
        }}

        .market-stats strong {{
            font-size: 18px;
        }}

        .top-section {{
            margin-bottom: 20px;
        }}

        .top-section h2 {{
            margin: 0 0 12px;
        }}

        .top-cards {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 14px;
        }}

        .top-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        }}

        .top-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .stock-name {{
            font-size: 20px;
            font-weight: 900;
        }}

        .priority-line {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }}

        .mini-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            margin-bottom: 12px;
        }}

        .mini-grid div {{
            background: #f9fafb;
            padding: 10px;
            border-radius: 10px;
            border: 1px solid var(--border);
        }}

        .mini-grid span {{
            color: var(--muted);
            display: block;
            font-size: 12px;
        }}

        .mini-grid strong {{
            font-size: 15px;
        }}

        .position-box {{
            background: #eff6ff;
            color: #1e3a8a;
            padding: 12px;
            border-radius: 12px;
            font-size: 13px;
            line-height: 1.5;
            margin-bottom: 10px;
        }}

        .small-note {{
            color: var(--muted);
            margin: 0;
            font-size: 13px;
        }}

        .explain {{
            background: #fff7ed;
            border-left: 6px solid #f97316;
            padding: 16px 20px;
            border-radius: 14px;
            margin-bottom: 20px;
            line-height: 1.55;
            font-size: 15px;
        }}

        .criteria {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 18px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}

        .criteria h2 {{
            margin-top: 0;
            margin-bottom: 14px;
        }}

        .criteria-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
        }}

        .criteria-item {{
            background: #f9fafb;
            border: 1px solid var(--border);
            padding: 14px;
            border-radius: 12px;
            line-height: 1.45;
        }}

        .criteria-item strong {{
            display: block;
            margin-bottom: 6px;
        }}

        .table-wrap {{
            overflow-x: auto;
            background: var(--card);
            border-radius: 16px;
            border: 1px solid var(--border);
            box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        }}

        table {{
            width: 100%;
            min-width: 1800px;
            border-collapse: collapse;
        }}

        th {{
            background: var(--dark);
            color: white;
            text-align: left;
            padding: 11px 10px;
            font-size: 12px;
            white-space: nowrap;
            position: sticky;
            top: 0;
        }}

        td {{
            padding: 9px 10px;
            border-bottom: 1px solid var(--border);
            font-size: 12.5px;
            vertical-align: middle;
            line-height: 1.2;
            white-space: nowrap;
        }}

        .row-high {{
            background: var(--green-row);
        }}

        .row-medium {{
            background: var(--yellow-row);
        }}

        .row-low {{
            background: var(--orange-row);
        }}

        .stock {{
            font-weight: 900;
            color: #111827;
        }}

        .score {{
            font-weight: 900;
            font-size: 14px;
        }}

        .badge {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-weight: 800;
            font-size: 11px;
        }}

        .buy {{
            background: var(--green-bg);
            color: var(--green);
        }}

        .sell {{
            background: var(--red-bg);
            color: var(--red);
        }}

        .priority {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 800;
        }}

        .priority-high {{
            background: var(--green-bg);
            color: var(--green);
        }}

        .priority-medium {{
            background: var(--yellow-bg);
            color: var(--yellow);
        }}

        .priority-low {{
            background: var(--orange-bg);
            color: var(--orange);
        }}

        .priority-avoid {{
            background: #e5e7eb;
            color: #374151;
        }}

        .empty,
        .empty-card {{
            text-align: center;
            padding: 30px;
            font-size: 16px;
            color: var(--muted);
            background: var(--card);
            border-radius: 16px;
            border: 1px solid var(--border);
        }}
<section class="performance-section">
    <h2>📊 Top 3 Performance Log</h2>
    <p class="section-note">
        This log tracks the platform's Top 3 daily picks. The latest 60 trade ideas appear first.
        Older records are grouped into 60-trade tabs.
    </p>
    {performance_log_html}
</section>
        .footer {{
            margin-top: 20px;
            color: var(--muted);
            font-size: 13px;
            line-height: 1.5;
        }}
.performance-section {
    margin-top: 24px;
}

.performance-section h2 {
    margin-bottom: 6px;
}

.section-note {
    color: var(--muted);
    margin-top: 0;
    margin-bottom: 14px;
    font-size: 14px;
}

.tab-buttons {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}

.tab-button {
    border: 1px solid var(--border);
    background: white;
    color: #374151;
    padding: 9px 14px;
    border-radius: 999px;
    font-weight: 800;
    cursor: pointer;
}

.tab-button.active {
    background: var(--dark);
    color: white;
}

.performance-table table {
    min-width: 1300px;
}

.status-pill {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
    white-space: nowrap;
}

.status-win {
    background: var(--green-bg);
    color: var(--green);
}

.status-loss {
    background: var(--red-bg);
    color: var(--red);
}

.status-triggered {
    background: var(--blue-bg);
    color: var(--blue);
}

.status-pending {
    background: var(--yellow-bg);
    color: var(--yellow);
}

.status-expired {
    background: #e5e7eb;
    color: #374151;
}

.status-gap {
    background: var(--orange-bg);
    color: var(--orange);
}

.status-neutral {
    background: #f3f4f6;
    color: #374151;
}
        @media (max-width: 1000px) {{
            body {{
                padding: 16px;
            }}

            .metrics {{
                grid-template-columns: 1fr 1fr;
            }}

            .market-box {{
                grid-template-columns: 1fr;
            }}

            .market-stats {{
                grid-template-columns: 1fr 1fr;
            }}

            .top-cards {{
                grid-template-columns: 1fr;
            }}

            .criteria-grid {{
                grid-template-columns: 1fr;
            }}

            .header h1 {{
                font-size: 28px;
            }}
        }}
    </style>
</head>

<body>
<div class="container">

    <section class="header">
        <h1>📈 High-Conviction Swing Trading Scanner</h1>
        <p>Generated on {datetime.now().strftime("%d %B %Y, %I:%M %p")} · NIFTY 500 watchlist · Educational research dashboard</p>
    </section>

    <section class="metrics">
        <div class="metric">
            <span>Total Candidates</span>
            <strong>{total}</strong>
        </div>
        <div class="metric">
            <span>Highest Priority</span>
            <strong>{high_count}</strong>
        </div>
        <div class="metric">
            <span>Medium Priority</span>
            <strong>{medium_count}</strong>
        </div>
        <div class="metric">
            <span>Low Priority</span>
            <strong>{low_count}</strong>
        </div>
        <div class="metric">
            <span>Best Conviction</span>
            <strong>{round(best_score, 1) if best_score else 0}</strong>
        </div>
        <div class="metric">
            <span>Avg Risk/Reward</span>
            <strong>{round(avg_rr, 2) if avg_rr else 0}</strong>
        </div>
    </section>

    <section class="market-box">
        <div>
            <span class="bias-pill {market["class"]}">NIFTY Bias: {market["bias"]}</span>
            <p>{market["text"]}</p>
        </div>
        <div class="market-stats">
            <div><span>NIFTY Close</span><strong>{market["close"]}</strong></div>
            <div><span>EMA 20</span><strong>{market["ema20"]}</strong></div>
            <div><span>EMA 50</span><strong>{market["ema50"]}</strong></div>
            <div><span>5-Day Change</span><strong>{market["change_5d"]}%</strong></div>
        </div>
    </section>

    <section class="top-section">
        <h2>Top 3 Setups</h2>
        <div class="top-cards">
            {top_cards}
        </div>
    </section>

    <section class="explain">
        <strong>Quick reading guide:</strong>
        Green rows are the strongest setups, yellow rows are decent setups, and orange rows are lower-conviction setups.
        Enter only if the price crosses the trigger in the direction of the signal. Position size is calculated using
        ₹{round(TOTAL_CAPITAL):,} capital and {RISK_PER_TRADE_PCT}% risk per trade.
    </section>

    <section class="criteria">
        <h2>Suggested Investment Criteria</h2>
        <div class="criteria-grid">
            <div class="criteria-item">
                <strong>85+ · Highest Priority</strong>
                Best setups. Consider only if trigger breaks with strong volume and market direction supports it.
            </div>
            <div class="criteria-item">
                <strong>80–84 · Medium Priority</strong>
                Decent setups. Use smaller size or wait for stronger confirmation.
            </div>
            <div class="criteria-item">
                <strong>75–79 · Low Priority</strong>
                Trade only with extra confirmation. Otherwise skip.
            </div>
            <div class="criteria-item">
                <strong>Risk Rule</strong>
                Suggested quantity uses fixed-risk sizing and max allocation cap.
            </div>
        </div>
    </section>

    <section class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>Priority</th>
                    <th>Stock</th>
                    <th>Signal</th>
                    <th>Conviction</th>
                    <th>Grade</th>
                    <th>Close</th>
                    <th>Entry</th>
                    <th>Stop</th>
                    <th>Target</th>
                    <th>RR</th>
                    <th>RSI</th>
                    <th>ATR%</th>
                    <th>Vol Ratio</th>
                    <th>RS vs NIFTY</th>
                    <th>Dist. Trigger</th>
                    <th>Qty</th>
                    <th>Trade Value</th>
                    <th>Entry Rule</th>
                    <th>Market Warning</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
            .performance-section {
    margin-top: 24px;
}

.performance-section h2 {
    margin-bottom: 6px;
}

.section-note {
    color: var(--muted);
    margin-top: 0;
    margin-bottom: 14px;
    font-size: 14px;
}

.tab-buttons {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}

.tab-button {
    border: 1px solid var(--border);
    background: white;
    color: #374151;
    padding: 9px 14px;
    border-radius: 999px;
    font-weight: 800;
    cursor: pointer;
}

.tab-button.active {
    background: var(--dark);
    color: white;
}

.performance-table table {
    min-width: 1300px;
}

.status-pill {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
    white-space: nowrap;
}

.status-win {
    background: var(--green-bg);
    color: var(--green);
}

.status-loss {
    background: var(--red-bg);
    color: var(--red);
}

.status-triggered {
    background: var(--blue-bg);
    color: var(--blue);
}

.status-pending {
    background: var(--yellow-bg);
    color: var(--yellow);
}

.status-expired {
    background: #e5e7eb;
    color: #374151;
}

.status-gap {
    background: var(--orange-bg);
    color: var(--orange);
}

.status-neutral {
    background: #f3f4f6;
    color: #374151;
}
                {html_rows}
            </tbody>
        </table>
    </section>

    <p class="footer">
        Disclaimer: This dashboard is for educational and research purposes only. It is not financial advice or a recommendation.
        Always verify chart structure, market trend, liquidity, news flow, event risk, and your personal risk limits before trading.
    </p>

</div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Upgraded dashboard report created: index.html")