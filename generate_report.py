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
    if "BUY" in str(signal).upper():
        return "buy"
    if "SELL" in str(signal).upper():
        return "sell"
    return "neutral"

def grade_class(grade):
    if str(grade).upper() == "A":
        return "grade-a"
    if str(grade).upper() == "B+":
        return "grade-b"
    return "grade-neutral"

def action_text(signal):
    if "BUY" in str(signal).upper():
        return "Enter only if price moves above Entry Trigger with strong volume."
    if "SELL" in str(signal).upper():
        return "Enter only if price breaks below Entry Trigger with strong volume."
    return "Wait for confirmation."

# ---------------- SUMMARY METRICS ----------------

total = len(df)
buy_count = len(df[df["Signal"].astype(str).str.contains("BUY", case=False, na=False)]) if not df.empty and "Signal" in df.columns else 0
sell_count = len(df[df["Signal"].astype(str).str.contains("SELL", case=False, na=False)]) if not df.empty and "Signal" in df.columns else 0
best_score = df["Conviction Score"].max() if not df.empty and "Conviction Score" in df.columns else 0
avg_rr = df["Risk/Reward"].mean() if not df.empty and "Risk/Reward" in df.columns else 0

# ---------------- TABLE ROWS ----------------

if df.empty:
    html_rows = """
    <tr>
        <td colspan="17" class="empty">
            No high-conviction trade candidates today. This is acceptable — no trade is also a valid trading decision.
        </td>
    </tr>
    """
else:
    html_rows = ""

    for _, row in df.iterrows():
        signal = safe_value(row, "Signal")
        grade = safe_value(row, "Grade")
        explanation = safe_value(row, "Explanation")
        avoid_if = safe_value(row, "Avoid If")
        suggested_action = safe_value(row, "Suggested Action")

        html_rows += f"""
        <tr>
            <td class="stock">{safe_value(row, "Symbol")}</td>
            <td><span class="badge {badge_class(signal)}">{signal}</span></td>
            <td><span class="grade {grade_class(grade)}">{grade}</span></td>
            <td class="score">{safe_value(row, "Conviction Score")}</td>
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
            <td>{action_text(signal)}</td>
            <td>{avoid_if}</td>
            <td>{explanation}</td>
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
            --dark: #111827;
            --green: #047857;
            --green-bg: #d1fae5;
            --red: #b91c1c;
            --red-bg: #fee2e2;
            --orange: #f97316;
            --orange-bg: #fff7ed;
            --blue: #1d4ed8;
            --blue-bg: #dbeafe;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            padding: 28px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
        }}

        .container {{
            max-width: 1500px;
            margin: 0 auto;
        }}

        .header {{
            margin-bottom: 26px;
        }}

        .header h1 {{
            font-size: 38px;
            margin: 0 0 8px;
            letter-spacing: -0.8px;
        }}

        .header p {{
            color: var(--muted);
            margin: 0;
            font-size: 16px;
        }}

        .metrics {{
            display: grid;
            grid-template-columns: repeat(5, minmax(160px, 1fr));
            gap: 16px;
            margin-bottom: 26px;
        }}

        .metric {{
            background: var(--card);
            padding: 20px;
            border-radius: 16px;
            box-shadow: 0 3px 14px rgba(0,0,0,0.07);
            border: 1px solid var(--border);
        }}

        .metric span {{
            color: var(--muted);
            font-size: 14px;
            font-weight: 600;
        }}

        .metric strong {{
            display: block;
            font-size: 28px;
            margin-top: 8px;
        }}

        .explain {{
            background: var(--orange-bg);
            border-left: 6px solid var(--orange);
            padding: 20px 24px;
            border-radius: 16px;
            margin-bottom: 22px;
            line-height: 1.65;
            font-size: 15px;
        }}

        .explain h2 {{
            margin: 0 0 8px;
            font-size: 20px;
        }}

        .rules {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 18px;
            margin-bottom: 24px;
        }}

        .rule-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 3px 14px rgba(0,0,0,0.06);
        }}

        .rule-card h3 {{
            margin: 0 0 12px;
            font-size: 19px;
        }}

        .rule-card ul {{
            margin: 0;
            padding-left: 20px;
            line-height: 1.65;
            color: #374151;
        }}

        .criteria {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 3px 14px rgba(0,0,0,0.06);
        }}

        .criteria h2 {{
            margin-top: 0;
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
        }}

        .criteria-item strong {{
            display: block;
            margin-bottom: 6px;
        }}

        .table-wrap {{
            overflow-x: auto;
            background: var(--card);
            border-radius: 18px;
            border: 1px solid var(--border);
            box-shadow: 0 3px 14px rgba(0,0,0,0.08);
        }}

        table {{
            width: 100%;
            min-width: 1700px;
            border-collapse: collapse;
        }}

        th {{
            background: var(--dark);
            color: white;
            text-align: left;
            padding: 14px 12px;
            font-size: 13px;
            white-space: nowrap;
        }}

        td {{
            padding: 14px 12px;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
            vertical-align: top;
            color: #1f2937;
        }}

        tr:hover {{
            background: #f9fafb;
        }}

        .stock {{
            font-weight: 800;
            color: #111827;
            white-space: nowrap;
        }}

        .badge {{
            display: inline-block;
            padding: 7px 10px;
            border-radius: 999px;
            font-weight: 800;
            font-size: 12px;
            white-space: nowrap;
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

        .grade {{
            display: inline-block;
            min-width: 44px;
            text-align: center;
            padding: 7px 10px;
            border-radius: 10px;
            font-weight: 800;
        }}

        .grade-a {{
            background: var(--green-bg);
            color: var(--green);
        }}

        .grade-b {{
            background: var(--blue-bg);
            color: var(--blue);
        }}

        .grade-neutral {{
            background: #e5e7eb;
            color: #374151;
        }}

        .score {{
            font-weight: 900;
            font-size: 15px;
        }}

        .empty {{
            text-align: center;
            padding: 40px;
            font-size: 16px;
            color: var(--muted);
        }}

        .footer {{
            margin-top: 24px;
            color: var(--muted);
            font-size: 13px;
            line-height: 1.6;
        }}

        @media (max-width: 900px) {{
            body {{
                padding: 18px;
            }}

            .metrics {{
                grid-template-columns: 1fr 1fr;
            }}

            .rules {{
                grid-template-columns: 1fr;
            }}

            .criteria-grid {{
                grid-template-columns: 1fr;
            }}

            .header h1 {{
                font-size: 30px;
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
            <span>BUY Setups</span>
            <strong>{buy_count}</strong>
        </div>
        <div class="metric">
            <span>SELL Setups</span>
            <strong>{sell_count}</strong>
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
        <h2>How to read this report</h2>
        <strong>BUY</strong> means the stock is showing bullish strength and is close to a breakout trigger.
        <strong>SELL</strong> means the stock is showing weakness and is close to a breakdown trigger.
        Do not enter just because the stock appears in the table. Enter only if the price crosses the
        <strong>Entry Trigger</strong> with convincing volume. The <strong>Stop Loss</strong> defines your risk,
        the <strong>Target</strong> defines the reward zone, and the <strong>Conviction Score</strong> ranks setup quality.
    </section>

    <section class="rules">
        <div class="rule-card">
            <h3>✅ Entry Rules</h3>
            <ul>
                <li>For BUY: price must move above the Entry Trigger.</li>
                <li>For SELL: price must move below the Entry Trigger.</li>
                <li>Prefer trades where market direction supports the trade.</li>
                <li>Use the Stop Loss exactly; do not average losing trades.</li>
                <li>Risk only a small fixed percentage of capital per trade.</li>
            </ul>
        </div>

        <div class="rule-card">
            <h3>🚫 Avoid Rules</h3>
            <ul>
                <li>Avoid if price opens far beyond the trigger; do not chase.</li>
                <li>Avoid if volume is weak at the trigger.</li>
                <li>Avoid BUY trades if NIFTY is sharply weak.</li>
                <li>Avoid SELL trades if NIFTY is sharply strong.</li>
                <li>Avoid if the setup is near major news, results, or event risk.</li>
            </ul>
        </div>
    </section>

    <section class="criteria">
        <h2>Suggested Investment Criteria</h2>
        <div class="criteria-grid">
            <div class="criteria-item">
                <strong>Conviction 85–100</strong>
                Grade A. Best setups. Consider only if trigger breaks with strong volume.
            </div>
            <div class="criteria-item">
                <strong>Conviction 75–84</strong>
                Grade B+. Watchlist. Use smaller position or wait for stronger confirmation.
            </div>
            <div class="criteria-item">
                <strong>Conviction below 75</strong>
                Not shown. Setup is too weak for this scanner.
            </div>
            <div class="criteria-item">
                <strong>Risk Rule</strong>
                Avoid any trade where risk/reward is below 2.5.
            </div>
        </div>
    </section>

    <section class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>Stock</th>
                    <th>Signal</th>
                    <th>Grade</th>
                    <th>Conviction</th>
                    <th>Close</th>
                    <th>Entry Trigger</th>
                    <th>Stop Loss</th>
                    <th>Target</th>
                    <th>Risk/Reward</th>
                    <th>RSI</th>
                    <th>ATR%</th>
                    <th>Volume Ratio</th>
                    <th>Rel. Strength vs NIFTY</th>
                    <th>Distance to Trigger</th>
                    <th>When to Enter</th>
                    <th>When to Avoid</th>
                    <th>Why It Qualified</th>
                </tr>
            </thead>
            <tbody>
                {html_rows}
            </tbody>
        </table>
    </section>

    <p class="footer">
        Disclaimer: This dashboard is for educational and research use only. It is not financial advice or a recommendation to buy or sell securities.
        Always verify chart structure, news flow, liquidity, results calendar, market trend, and your personal risk limits before taking any trade.
    </p>

</div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Updated high-conviction report created: index.html")