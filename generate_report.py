import pandas as pd
from datetime import datetime
from pathlib import Path


OUTPUT_CSV = "scanner_output.csv"
OUTPUT_HTML = "index.html"


def safe_value(row, column, default="-"):
    try:
        value = row.get(column, default)
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def format_number(value, decimals=2):
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)


def get_priority(row):
    for col in ["Priority", "priority", "Signal Priority", "signal_priority"]:
        val = safe_value(row, col, "")
        if val != "":
            return str(val)
    return "Watchlist"


def get_score(row):
    for col in ["Score", "score", "Conviction", "conviction", "Conviction Score"]:
        val = safe_value(row, col, None)
        if val not in [None, "-"]:
            return val
    return "-"


def get_symbol(row):
    for col in ["Symbol", "symbol", "Ticker", "ticker"]:
        val = safe_value(row, col, "")
        if val != "":
            return str(val)
    return "-"


def get_grade(row):
    for col in ["Grade", "grade"]:
        val = safe_value(row, col, "")
        if val != "":
            return str(val)
    return "-"


def get_explanation(row):
    for col in ["Explanation", "explanation", "Reason", "reason", "Setup", "setup"]:
        val = safe_value(row, col, "")
        if val != "":
            return str(val)
    return "High-conviction swing-trading candidate based on scanner filters."


def priority_class(priority):
    p = str(priority).lower()
    if "highest" in p:
        return "priority-highest"
    if "medium" in p:
        return "priority-medium"
    if "low" in p:
        return "priority-low"
    return "priority-neutral"


def load_results():
    path = Path(OUTPUT_CSV)
    if not path.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        print(f"Could not read {OUTPUT_CSV}: {e}")
        return pd.DataFrame()


def build_rows(df):
    if df.empty:
        return """
        <tr>
            <td colspan="8" class="empty-state">
                No scanner candidates found in the latest run.
            </td>
        </tr>
        """

    rows = []

    for _, row in df.iterrows():
        symbol = get_symbol(row)
        priority = get_priority(row)
        score = get_score(row)
        grade = get_grade(row)
        explanation = get_explanation(row)

        close = "-"
        for col in ["Close", "close", "Last Close", "last_close", "Price", "price"]:
            value = safe_value(row, col, "")
            if value != "":
                close = format_number(value)
                break

        rr = "-"
        for col in ["Risk/Reward", "risk_reward", "RiskReward", "RR", "rr"]:
            value = safe_value(row, col, "")
            if value != "":
                rr = format_number(value)
                break

        target = "-"
        for col in ["Target", "target", "Target Price", "target_price"]:
            value = safe_value(row, col, "")
            if value != "":
                target = format_number(value)
                break

        stop_loss = "-"
        for col in ["Stop Loss", "stop_loss", "SL", "sl"]:
            value = safe_value(row, col, "")
            if value != "":
                stop_loss = format_number(value)
                break

        rows.append(f"""
        <tr>
            <td class="symbol">{symbol}</td>
            <td><span class="badge {priority_class(priority)}">{priority}</span></td>
            <td>{format_number(score, 0) if score != "-" else "-"}</td>
            <td>{grade}</td>
            <td>{close}</td>
            <td>{target}</td>
            <td>{stop_loss}</td>
            <td>{rr}</td>
            <td class="explanation">{explanation}</td>
        </tr>
        """)

    return "\n".join(rows)


def count_priority(df, keyword):
    if df.empty:
        return 0

    count = 0
    for _, row in df.iterrows():
        priority = get_priority(row).lower()
        if keyword.lower() in priority:
            count += 1
    return count


def best_score(df):
    if df.empty:
        return "-"

    scores = []
    for _, row in df.iterrows():
        score = get_score(row)
        try:
            scores.append(float(score))
        except Exception:
            pass

    if not scores:
        return "-"
    return f"{max(scores):.0f}"


def avg_risk_reward(df):
    if df.empty:
        return "-"

    values = []
    for _, row in df.iterrows():
        for col in ["Risk/Reward", "risk_reward", "RiskReward", "RR", "rr"]:
            value = safe_value(row, col, "")
            if value != "":
                try:
                    values.append(float(value))
                except Exception:
                    pass
                break

    if not values:
        return "-"
    return f"{sum(values) / len(values):.2f}"


def get_market_bias(df):
    if df.empty:
        return "Mixed", "Market data was not sufficient for this run. Avoid forcing trades."

    highest = count_priority(df, "highest")
    medium = count_priority(df, "medium")
    total = len(df)

    if highest >= 3:
        return "Bullish", "Market breadth looks constructive. Focus on highest-conviction setups with disciplined stop losses."
    if highest >= 1 or medium >= max(3, total // 2):
        return "Selective", "Market has some usable setups. Prefer cleaner charts with strong relative strength."
    return "Mixed", "Market is mixed. Prefer only the highest-conviction setups."


def generate_html():
    df = load_results()

    generated_time = datetime.now().strftime("%d %b %Y, %I:%M %p")

    total_candidates = len(df)
    highest_count = count_priority(df, "highest")
    medium_count = count_priority(df, "medium")
    low_count = count_priority(df, "low")
    best_conviction = best_score(df)
    avg_rr = avg_risk_reward(df)
    bias, bias_text = get_market_bias(df)
    html_rows = build_rows(df)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>High-Conviction Swing Trading Scanner</title>
    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            background: #f5f7fb;
            color: #111827;
        }}

        .page {{
            max-width: 1180px;
            margin: 0 auto;
            padding: 32px 22px 56px;
        }}

        .topbar {{
            margin-bottom: 28px;
        }}

        .back-link {{
            display: inline-block;
            padding: 12px 18px;
            border-radius: 999px;
            background: #ffffff;
            color: #2563eb;
            text-decoration: none;
            font-weight: 700;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
        }}

        h1 {{
            font-size: clamp(34px, 6vw, 64px);
            line-height: 1.05;
            margin: 0 0 14px;
            letter-spacing: -0.045em;
        }}

        .subtitle {{
            color: #6b7280;
            font-size: 18px;
            font-weight: 650;
            margin-bottom: 28px;
        }}

        .cards {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 18px;
            margin-bottom: 26px;
        }}

        .card {{
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 22px;
            padding: 22px;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
        }}

        .card-label {{
            color: #6b7280;
            font-weight: 750;
            font-size: 16px;
            margin-bottom: 10px;
        }}

        .card-value {{
            font-size: 38px;
            font-weight: 850;
            letter-spacing: -0.04em;
        }}

        .bias-box {{
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 24px;
            padding: 26px;
            margin-bottom: 26px;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
        }}

        .bias-pill {{
            display: inline-block;
            padding: 10px 18px;
            border-radius: 999px;
            background: #fef3c7;
            color: #92400e;
            font-weight: 850;
            letter-spacing: 0.04em;
            margin-bottom: 18px;
        }}

        .bias-text {{
            font-size: 22px;
            font-weight: 750;
            line-height: 1.35;
            margin: 0;
        }}

        .table-card {{
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 24px;
            padding: 0;
            overflow: hidden;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
        }}

        .table-header {{
            padding: 22px 24px;
            border-bottom: 1px solid #e5e7eb;
        }}

        .table-header h2 {{
            margin: 0;
            font-size: 24px;
            letter-spacing: -0.02em;
        }}

        .table-wrap {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            min-width: 920px;
        }}

        th {{
            text-align: left;
            padding: 15px 18px;
            background: #f9fafb;
            color: #4b5563;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        td {{
            padding: 17px 18px;
            border-top: 1px solid #eef2f7;
            vertical-align: top;
            font-weight: 600;
        }}

        .symbol {{
            font-weight: 850;
            color: #111827;
        }}

        .badge {{
            display: inline-block;
            padding: 7px 11px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 850;
            white-space: nowrap;
        }}

        .priority-highest {{
            background: #dcfce7;
            color: #166534;
        }}

        .priority-medium {{
            background: #dbeafe;
            color: #1d4ed8;
        }}

        .priority-low {{
            background: #fef3c7;
            color: #92400e;
        }}

        .priority-neutral {{
            background: #f3f4f6;
            color: #374151;
        }}

        .explanation {{
            color: #4b5563;
            font-weight: 550;
            line-height: 1.45;
            min-width: 280px;
        }}

        .empty-state {{
            text-align: center;
            padding: 34px;
            color: #6b7280;
        }}

        .footer {{
            color: #6b7280;
            font-size: 14px;
            line-height: 1.5;
            margin-top: 24px;
        }}

        @media (max-width: 800px) {{
            .page {{
                padding: 24px 16px 44px;
            }}

            .cards {{
                grid-template-columns: repeat(2, 1fr);
                gap: 14px;
            }}

            .card {{
                padding: 18px;
                border-radius: 18px;
            }}

            .card-value {{
                font-size: 32px;
            }}

            .bias-text {{
                font-size: 20px;
            }}
        }}

        @media (max-width: 520px) {{
            .cards {{
                grid-template-columns: 1fr 1fr;
            }}

            .subtitle {{
                font-size: 16px;
            }}
        }}
    </style>
</head>
<body>
    <main class="page">
        <div class="topbar">
            <a class="back-link" href="https://pankajmanchnda.github.io/trading-agents/">
                ← Back to Trading Agents Dashboard
            </a>
        </div>

        <header>
            <h1>📈 High-Conviction Swing Trading Scanner</h1>
            <div class="subtitle">
                Generated on {generated_time} · NIFTY 500 watchlist · Educational research dashboard
            </div>
        </header>

        <section class="cards">
            <div class="card">
                <div class="card-label">Total Candidates</div>
                <div class="card-value">{total_candidates}</div>
            </div>

            <div class="card">
                <div class="card-label">Highest Priority</div>
                <div class="card-value">{highest_count}</div>
            </div>

            <div class="card">
                <div class="card-label">Medium Priority</div>
                <div class="card-value">{medium_count}</div>
            </div>

            <div class="card">
                <div class="card-label">Low Priority</div>
                <div class="card-value">{low_count}</div>
            </div>

            <div class="card">
                <div class="card-label">Best Conviction</div>
                <div class="card-value">{best_conviction}</div>
            </div>

            <div class="card">
                <div class="card-label">Avg Risk/Reward</div>
                <div class="card-value">{avg_rr}</div>
            </div>
        </section>

        <section class="bias-box">
            <div class="bias-pill">NIFTY Bias: {bias}</div>
            <p class="bias-text">{bias_text}</p>
        </section>

        <section class="table-card">
            <div class="table-header">
                <h2>Latest Scanner Candidates</h2>
            </div>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Priority</th>
                            <th>Score</th>
                            <th>Grade</th>
                            <th>Close</th>
                            <th>Target</th>
                            <th>Stop Loss</th>
                            <th>Risk/Reward</th>
                            <th>Explanation</th>
                        </tr>
                    </thead>
                    <tbody>
                        {html_rows}
                    </tbody>
                </table>
            </div>
        </section>

        <p class="footer">
            Disclaimer: This dashboard is for educational and research purposes only. It is not financial advice or a recommendation.
            Always verify chart structure, market trend, liquidity, news flow, event risk, and your personal risk limits before trading.
        </p>
    </main>
</body>
</html>
"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard report created: {OUTPUT_HTML}")


if __name__ == "__main__":
    generate_html()
