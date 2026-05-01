import pandas as pd
from datetime import datetime

# ---------------- LOAD DATA ----------------

try:
    df = pd.read_csv("scanner_output.csv")
except FileNotFoundError:
    df = pd.DataFrame()

# ---------------- HELPERS ----------------

def safe_value(row, col, default="-"):
    return row[col] if col in row and pd.notna(row[col]) else default

def badge_class(signal):
    s = str(signal).upper()
    if "BUY" in s:
        return "buy"
    if "SELL" in s:
        return "sell"
    return "neutral"

def priority_info(score):
    try:
        score = float(score)
    except:
        score = 0

    if score >= 85:
        return ("Must Trade", "priority-must", "row-must")
    elif score >= 80:
        return ("Medium", "priority-medium", "row-medium")
    else:
        return ("Low", "priority-low", "row-low")

def compact_action(signal):
    s = str(signal).upper()
    if "BUY" in s:
        return "Enter only above trigger"
    if "SELL" in s:
        return "Enter only below trigger"
    return "Wait"

def compact_notes(row):
    signal = str(safe_value(row, "Signal", "")).upper()
    rs = safe_value(row, "Relative Strength vs NIFTY", 0)
    vol = safe_value(row, "Volume Ratio", 0)

    try:
        rs = float(rs)
    except:
        rs = 0

    try:
        vol = float(vol)
    except:
        vol = 0

    rs_text = "Strong RS" if abs(rs) >= 8 else "Decent RS"
    vol_text = "Strong volume" if vol >= 1.5 else "Normal volume"

    if "BUY" in signal:
        return f"Uptrend · {rs_text} · {vol_text}"
    elif "SELL" in signal:
        return f"Downtrend · {rs_text} · {vol_text}"
    return "Watch"

# ---------------- SUMMARY METRICS ----------------

if not df.empty and "Signal" in df.columns:
    buy_count = len(df[df["Signal"].astype(str).str.contains("BUY", case=False, na=False)])
    sell_count = len(df[df["Signal"].astype(str).str.contains("SELL", case=False, na=False)])
else:
    buy_count = 0
    sell_count = 0

if not df.empty and "Conviction Score" in df.columns:
    must_count = len(df[df["Conviction Score"] >= 85])
    medium_count = len(df[(df["Conviction Score"] >= 80) & (df["Conviction Score"] < 85)])
    low_count = len(df[(df["Conviction Score"] >= 75) & (df["Conviction Score"] < 80)])
    best_score = df["Conviction Score"].max()
else:
    must_count = medium_count = low_count = 0
    best_score = 0

avg_rr = df["Risk/Reward"].mean() if not df.empty and "Risk/Reward" in df.columns else 0
total = len(df)

# ---------------- TABLE ROWS ----------------

if df.empty:
    html_rows = """
    <tr>
        <td colspan="15" class="empty">
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

        html_rows += f"""
        <tr class="{row_class}">
            <td><span class="priority {priority_class}">{priority_text}</span></td>
            <td class="stock">{safe_value(row, "Symbol")}</td>
            <td><span class="badge {badge_class(signal)}">{signal}</span></td>
            <td class="score">{safe_value(row, "Conviction Score")}</td>
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
            <td>{compact_action(signal)}</td>
            <td>{compact_notes(row)}</td>
        </tr>
        """

# ---------------- HTML ----------------

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
            max-width: 1500px;
            margin: 0 auto;
        }}

        .header {{
            margin-bottom: 24px;
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
            margin-bottom: 22px;
        }}

        .metric {{
            background: var(--card);
            padding: 18px;
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
            font-size: 26px;
            margin-top: 8px;
        }}

        .explain {{
            background: #fff7ed;
            border-left: 6px solid #f97316;
            padding: 18px 22px;
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
            min-width: 1500px;
            border-collapse: collapse;
        }}

        th {{
            background: var(--dark);
            color: white;
            text-align: left;
            padding: 12px 10px;
            font-size: 13px;
            white-space: nowrap;
            position: sticky;
            top: 0;
        }}

        td {{
            padding: 10px 10px;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
            vertical-align: middle;
            line-height: 1.25;
            white-space: nowrap;
        }}

        tr:hover {{
            filter: brightness(0.99);
        }}

        .row-must {{
            background: var(--green-row);
        }}

        .row-medium {{
            background: var(--yellow-row);
        }}

        .row-low {{
            background: var(--orange-row);
        }}

        .stock {{
            font-weight: 800;
            color: #111827;
        }}

        .score {{
            font-weight: 900;
            font-size: 15px;
        }}

        .badge {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-weight: 800;
            font-size: 12px;
        }}

        .buy {{
            background: var(--green-bg);
            color: var(--green);
        }}

        .sell {{
            background: var(--red-bg);
            color: var(--red);
        }}

        .neutral {{
            background: #e5e7eb;
            color: #374151;
        }}

        .priority {{
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 800;
        }}

        .priority-must {{
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

        .empty {{
            text-align: center;
            padding: 30px;
            font-size: 16px;
            color: var(--muted);
        }}

        .footer {{
            margin-top: 20px;
            color: var(--muted);
            font-size: 13px;
            line-height: 1.5;
        }}

        @media (max-width: 900px) {{
            body {{
                padding: 16px;
            }}

            .metrics {{
                grid-template-columns: 1fr 1fr;
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
            <span>Must Trade</span>
            <strong>{must_count}</strong>
        </div>
        <div class="metric">
            <span>Medium</span>
            <strong>{medium_count}</strong>
        </div>
        <div class="metric">
            <span>Low</span>
            <strong>{low_count}</strong>
        </div>
        <div class="metric">
            <span>Best Conviction</span>
            <strong>{round(best_score, 1) if best_score else 0}</strong>
        </div>
        <div class="metric">
            <span>Average Risk/Reward</span>
            <strong>{round(avg_rr, 2) if avg_rr else 0}</strong>
        </div>
    </section>

    <section class="explain">
        <strong>Quick reading guide:</strong>
        Green rows are the strongest setups, yellow rows are decent setups, and orange rows are lower-conviction setups.
        Enter only if the price crosses the trigger in the direction of the signal. Avoid chasing if the opening price is already too far beyond the trigger.
    </section>

    <section class="criteria">
        <h2>Suggested Investment Criteria</h2>
        <div class="criteria-grid">
            <div class="criteria-item">
                <strong>Green · 85+</strong>
                Must Trade. Best setups. Consider only if trigger breaks with strong volume.
            </div>
            <div class="criteria-item">
                <strong>Yellow · 80–84</strong>
                Medium conviction. Good watchlist names. Smaller position size.
            </div>
            <div class="criteria-item">
                <strong>Orange · 75–79</strong>
                Low conviction. Trade only with extra confirmation.
            </div>
            <div class="criteria-item">
                <strong>Risk Rule</strong>
                Avoid any trade where risk/reward is below 2.5 or the trigger is badly chased.
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
                    <th>Entry Trigger</th>
                    <th>Stop Loss</th>
                    <th>Target</th>
                    <th>Risk/Reward</th>
                    <th>RSI</th>
                    <th>ATR%</th>
                    <th>Volume Ratio</th>
                    <th>Rel. Strength vs NIFTY</th>
                    <th>When to Enter</th>
                    <th>Setup Notes</th>
                </tr>
            </thead>
            <tbody>
                {html_rows}
            </tbody>
        </table>
    </section>

    <p class="footer">
        Disclaimer: This dashboard is for educational and research purposes only. Always verify market trend, news flow, event risk, and position sizing before taking a trade.
    </p>

</div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Compact color-coded report created: index.html")