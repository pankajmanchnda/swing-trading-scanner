import html
from pathlib import Path
from datetime import datetime

import pandas as pd


OUTPUT_CSV = "scanner_output.csv"
OUTPUT_HTML = "index.html"


# ---------------- BASIC HELPERS ----------------

def read_csv_safely(path):
    file_path = Path(path)

    if not file_path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(file_path)
    except Exception as e:
        print(f"Could not read {path}: {e}")
        return pd.DataFrame()


def clean_value(value, default="-"):
    try:
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def get_col(row, possible_columns, default="-"):
    for col in possible_columns:
        if col in row.index:
            value = clean_value(row[col], default)
            if value != "":
                return value
    return default


def to_float(value, default=None):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def fmt_number(value, decimals=2, default="-"):
    num = to_float(value, None)
    if num is None:
        return default

    if decimals == 0:
        return f"{num:.0f}"

    return f"{num:.{decimals}f}"


def esc(value):
    return html.escape(str(value))


# ---------------- PRIORITY LOGIC ----------------

def get_score(row):
    value = get_col(
        row,
        ["Conviction Score", "Score", "score", "Conviction", "conviction"],
        "-"
    )
    return to_float(value, None)


def get_priority_from_score(score):
    if score is None:
        return "Watchlist"

    if score >= 85:
        return "Highest Priority"
    if score >= 80:
        return "Medium Priority"
    if score >= 75:
        return "Low Priority"

    return "Watchlist"


def get_priority(row):
    direct_priority = get_col(
        row,
        ["Priority", "priority", "Signal Priority", "signal_priority"],
        ""
    )

    if direct_priority != "":
        return str(direct_priority)

    return get_priority_from_score(get_score(row))


def priority_class(priority):
    p = str(priority).lower()

    if "highest" in p:
        return "priority-highest"
    if "medium" in p:
        return "priority-medium"
    if "low" in p:
        return "priority-low"

    return "priority-watchlist"


def count_priority(df, keyword):
    if df.empty:
        return 0

    count = 0

    for _, row in df.iterrows():
        priority = get_priority(row).lower()
        if keyword.lower() in priority:
            count += 1

    return count


def best_conviction(df):
    if df.empty:
        return "-"

    scores = []

    for _, row in df.iterrows():
        score = get_score(row)
        if score is not None:
            scores.append(score)

    if not scores:
        return "-"

    return fmt_number(max(scores), 0)


def average_rr(df):
    if df.empty:
        return "-"

    values = []

    for _, row in df.iterrows():
        rr = get_col(row, ["Risk/Reward", "risk_reward", "RR", "rr"], "-")
        rr_float = to_float(rr, None)

        if rr_float is not None:
            values.append(rr_float)

    if not values:
        return "-"

    return fmt_number(sum(values) / len(values), 2)


def get_bias(df):
    if df.empty:
        return "Mixed", "Market data was not sufficient for this run. Avoid forcing trades."

    highest = count_priority(df, "highest")
    medium = count_priority(df, "medium")
    low = count_priority(df, "low")

    if highest >= 2:
        return "Constructive", "Market has multiple high-quality setups. Focus on the cleanest triggers and strict position sizing."

    if highest >= 1 or medium >= 3:
        return "Selective", "Market has tradable setups, but selectivity matters. Prefer only clean breakout or breakdown triggers."

    if medium >= 1 or low >= 1:
        return "Mixed", "Market is mixed. Prefer only the highest-conviction setups."

    return "Mixed", "Market data was not sufficient for this run. Avoid forcing trades."


# ---------------- ROW / CARD BUILDERS ----------------

def normalize_dataframe(df):
    if df.empty:
        return df

    if "Conviction Score" in df.columns:
        df = df.copy()
        df["_sort_score"] = pd.to_numeric(df["Conviction Score"], errors="coerce").fillna(0)
        df = df.sort_values("_sort_score", ascending=False)
        df = df.drop(columns=["_sort_score"])

    return df


def build_setup_cards(df):
    if df.empty:
        return """
        <div class="empty-panel">
            <h3>No active candidates</h3>
            <p>The scanner did not find candidates that passed the current high-conviction filters.</p>
        </div>
        """

    cards = []

    for _, row in df.head(3).iterrows():
        symbol = get_col(row, ["Symbol", "symbol", "Ticker", "ticker"], "-")
        signal = get_col(row, ["Signal", "signal"], "-")
        score = get_score(row)
        priority = get_priority(row)

        entry = get_col(row, ["Entry Trigger", "Entry", "entry", "Trigger"], "-")
        stop = get_col(row, ["Stop Loss", "stop_loss", "SL"], "-")
        target = get_col(row, ["Target", "target"], "-")
        rr = get_col(row, ["Risk/Reward", "risk_reward", "RR"], "-")
        close = get_col(row, ["Close", "close", "Price"], "-")
        rsi = get_col(row, ["RSI", "rsi"], "-")
        vol_ratio = get_col(row, ["Volume Ratio", "volume_ratio"], "-")
        action = get_col(row, ["Suggested Action", "Action", "action"], "Enter only if trigger breaks")
        explanation = get_col(row, ["Explanation", "explanation", "Reason"], "")

        cards.append(f"""
        <article class="setup-card">
            <div class="setup-top">
                <div>
                    <h3>{esc(symbol)} — {esc(signal)}</h3>
                    <div class="setup-meta">
                        <span class="pill {priority_class(priority)}">{esc(priority)}</span>
                        <span>Score {fmt_number(score, 0)}</span>
                    </div>
                </div>
            </div>

            <div class="setup-grid">
                <div>
                    <span>Close</span>
                    <strong>{fmt_number(close)}</strong>
                </div>
                <div>
                    <span>Entry</span>
                    <strong>{fmt_number(entry)}</strong>
                </div>
                <div>
                    <span>Stop</span>
                    <strong>{fmt_number(stop)}</strong>
                </div>
                <div>
                    <span>Target</span>
                    <strong>{fmt_number(target)}</strong>
                </div>
                <div>
                    <span>RR</span>
                    <strong>{fmt_number(rr, 2)}</strong>
                </div>
                <div>
                    <span>RSI</span>
                    <strong>{fmt_number(rsi, 1)}</strong>
                </div>
                <div>
                    <span>Volume</span>
                    <strong>{fmt_number(vol_ratio, 2)}x</strong>
                </div>
            </div>

            <p class="action-line">{esc(action)}</p>
            <p class="setup-explanation">{esc(explanation)}</p>
        </article>
        """)

    return "\n".join(cards)


def build_table_rows(df):
    if df.empty:
        return """
        <tr>
            <td colspan="10" class="empty-table">
                No scanner candidates found in the latest run.
            </td>
        </tr>
        """

    rows = []

    for _, row in df.iterrows():
        symbol = get_col(row, ["Symbol", "symbol", "Ticker", "ticker"], "-")
        signal = get_col(row, ["Signal", "signal"], "-")
        priority = get_priority(row)
        score = get_score(row)
        grade = get_col(row, ["Grade", "grade"], "-")
        close = get_col(row, ["Close", "close", "Price"], "-")
        entry = get_col(row, ["Entry Trigger", "Entry", "entry", "Trigger"], "-")
        target = get_col(row, ["Target", "target"], "-")
        stop = get_col(row, ["Stop Loss", "stop_loss", "SL"], "-")
        rr = get_col(row, ["Risk/Reward", "risk_reward", "RR"], "-")
        explanation = get_col(row, ["Explanation", "explanation", "Reason"], "-")

        rows.append(f"""
        <tr>
            <td class="symbol-cell">{esc(symbol)}</td>
            <td>{esc(signal)}</td>
            <td><span class="pill {priority_class(priority)}">{esc(priority)}</span></td>
            <td>{fmt_number(score, 0)}</td>
            <td>{esc(grade)}</td>
            <td>{fmt_number(close)}</td>
            <td>{fmt_number(entry)}</td>
            <td>{fmt_number(target)}</td>
            <td>{fmt_number(stop)}</td>
            <td>{fmt_number(rr, 2)}</td>
            <td class="explanation-cell">{esc(explanation)}</td>
        </tr>
        """)

    return "\n".join(rows)


# ---------------- HTML GENERATOR ----------------

def generate_html():
    df = read_csv_safely(OUTPUT_CSV)
    df = normalize_dataframe(df)

    generated_time = datetime.now().strftime("%d %b %Y, %I:%M %p")

    total_candidates = len(df)
    highest_count = count_priority(df, "highest")
    medium_count = count_priority(df, "medium")
    low_count = count_priority(df, "low")
    best_score = best_conviction(df)
    avg_rr = average_rr(df)

    bias, bias_text = get_bias(df)

    setup_cards = build_setup_cards(df)
    table_rows = build_table_rows(df)

    template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>High-Conviction Swing Trading Scanner</title>

    <style>
        :root {
            --bg: #f4f7fb;
            --card: #ffffff;
            --text: #0f172a;
            --muted: #64748b;
            --border: #e2e8f0;
            --blue: #2563eb;
            --green-bg: #dcfce7;
            --green-text: #166534;
            --blue-bg: #dbeafe;
            --blue-text: #1d4ed8;
            --yellow-bg: #fef3c7;
            --yellow-text: #92400e;
            --gray-bg: #f1f5f9;
            --gray-text: #475569;
            --shadow: 0 14px 35px rgba(15, 23, 42, 0.08);
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            background:
                radial-gradient(circle at top left, rgba(37, 99, 235, 0.08), transparent 30%),
                var(--bg);
            color: var(--text);
        }

        .page {
            max-width: 1180px;
            margin: 0 auto;
            padding: 30px 20px 60px;
        }

        .topbar {
            margin-bottom: 28px;
        }

        .back-link {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 13px 20px;
            border-radius: 999px;
            background: var(--card);
            color: var(--blue);
            text-decoration: none;
            font-weight: 800;
            box-shadow: var(--shadow);
            border: 1px solid var(--border);
        }

        .hero {
            margin-bottom: 26px;
        }

        .hero h1 {
            margin: 0 0 14px;
            font-size: clamp(42px, 6vw, 68px);
            line-height: 0.98;
            letter-spacing: -0.06em;
            font-weight: 900;
        }

        .subtitle {
            color: var(--muted);
            font-size: 18px;
            font-weight: 750;
            line-height: 1.5;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 18px;
            margin: 28px 0;
        }

        .stat-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 22px;
            box-shadow: var(--shadow);
        }

        .stat-label {
            color: var(--muted);
            font-size: 15px;
            font-weight: 800;
            margin-bottom: 10px;
        }

        .stat-value {
            font-size: 40px;
            line-height: 1;
            font-weight: 900;
            letter-spacing: -0.05em;
        }

        .bias-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 28px;
            box-shadow: var(--shadow);
            margin-bottom: 30px;
        }

        .bias-pill {
            display: inline-flex;
            padding: 10px 18px;
            border-radius: 999px;
            background: var(--yellow-bg);
            color: var(--yellow-text);
            font-weight: 900;
            letter-spacing: 0.04em;
            margin-bottom: 18px;
        }

        .bias-text {
            margin: 0;
            font-size: 24px;
            line-height: 1.35;
            font-weight: 800;
        }

        .section-title {
            margin: 34px 0 16px;
            font-size: 28px;
            font-weight: 900;
            letter-spacing: -0.03em;
        }

        .setup-list {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 18px;
            margin-bottom: 30px;
        }

        .setup-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 20px;
            box-shadow: var(--shadow);
        }

        .setup-card h3 {
            margin: 0 0 10px;
            font-size: 20px;
            letter-spacing: -0.03em;
        }

        .setup-meta {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
            color: var(--muted);
            font-weight: 800;
            margin-bottom: 18px;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 7px 11px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 900;
            white-space: nowrap;
        }

        .priority-highest {
            background: var(--green-bg);
            color: var(--green-text);
        }

        .priority-medium {
            background: var(--blue-bg);
            color: var(--blue-text);
        }

        .priority-low {
            background: var(--yellow-bg);
            color: var(--yellow-text);
        }

        .priority-watchlist {
            background: var(--gray-bg);
            color: var(--gray-text);
        }

        .setup-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }

        .setup-grid div {
            border: 1px solid var(--border);
            background: #f8fafc;
            border-radius: 14px;
            padding: 11px;
        }

        .setup-grid span {
            display: block;
            color: var(--muted);
            font-size: 13px;
            font-weight: 750;
            margin-bottom: 5px;
        }

        .setup-grid strong {
            font-size: 17px;
            font-weight: 900;
        }

        .action-line {
            margin: 16px 0 8px;
            font-weight: 850;
        }

        .setup-explanation {
            color: var(--muted);
            line-height: 1.45;
            margin: 0;
            font-weight: 600;
        }

        .table-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 24px;
            box-shadow: var(--shadow);
            overflow: hidden;
        }

        .table-heading {
            padding: 22px 24px;
            border-bottom: 1px solid var(--border);
        }

        .table-heading h2 {
            margin: 0;
            font-size: 25px;
            font-weight: 900;
            letter-spacing: -0.03em;
        }

        .table-wrap {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            min-width: 1120px;
        }

        th {
            background: #f8fafc;
            color: #475569;
            text-align: left;
            padding: 15px 18px;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 900;
            border-bottom: 1px solid var(--border);
        }

        td {
            padding: 16px 18px;
            border-bottom: 1px solid #edf2f7;
            vertical-align: top;
            font-weight: 700;
        }

        tr:hover td {
            background: #f8fafc;
        }

        .symbol-cell {
            font-weight: 950;
            color: #0f172a;
        }

        .explanation-cell {
            min-width: 320px;
            color: var(--muted);
            line-height: 1.45;
            font-weight: 600;
        }

        .empty-panel {
            grid-column: 1 / -1;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 28px;
            box-shadow: var(--shadow);
        }

        .empty-panel h3 {
            margin: 0 0 8px;
            font-size: 22px;
        }

        .empty-panel p {
            margin: 0;
            color: var(--muted);
            font-weight: 650;
        }

        .empty-table {
            text-align: center;
            padding: 36px;
            color: var(--muted);
        }

        .footer {
            margin-top: 24px;
            color: var(--muted);
            font-size: 14px;
            line-height: 1.55;
            font-weight: 600;
        }

        @media (max-width: 950px) {
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .setup-list {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 640px) {
            .page {
                padding: 24px 14px 44px;
            }

            .hero h1 {
                font-size: 42px;
            }

            .subtitle {
                font-size: 16px;
            }

            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }

            .stat-card {
                padding: 17px;
                border-radius: 18px;
            }

            .stat-value {
                font-size: 34px;
            }

            .bias-card {
                padding: 22px;
            }

            .bias-text {
                font-size: 21px;
            }

            .setup-card {
                padding: 18px;
            }
        }
    </style>
</head>

<body>
    <main class="page">
        <div class="topbar">
            <a class="back-link" href="https://pankajmanchnda.github.io/trading-agents/">
                ← Back to Trading Agents Dashboard
            </a>
        </div>

        <section class="hero">
            <h1>📈 High-Conviction Swing Trading Scanner</h1>
            <div class="subtitle">
                Generated on {{GENERATED_TIME}} · NIFTY 500 watchlist · Educational research dashboard
            </div>
        </section>

        <section class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Candidates</div>
                <div class="stat-value">{{TOTAL_CANDIDATES}}</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Highest Priority</div>
                <div class="stat-value">{{HIGHEST_COUNT}}</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Medium Priority</div>
                <div class="stat-value">{{MEDIUM_COUNT}}</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Low Priority</div>
                <div class="stat-value">{{LOW_COUNT}}</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Best Conviction</div>
                <div class="stat-value">{{BEST_SCORE}}</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Avg Risk/Reward</div>
                <div class="stat-value">{{AVG_RR}}</div>
            </div>
        </section>

        <section class="bias-card">
            <div class="bias-pill">NIFTY Bias: {{BIAS}}</div>
            <p class="bias-text">{{BIAS_TEXT}}</p>
        </section>

        <h2 class="section-title">Top 3 Setups</h2>

        <section class="setup-list">
            {{SETUP_CARDS}}
        </section>

        <section class="table-card">
            <div class="table-heading">
                <h2>Latest Scanner Candidates</h2>
            </div>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Signal</th>
                            <th>Priority</th>
                            <th>Score</th>
                            <th>Grade</th>
                            <th>Close</th>
                            <th>Entry</th>
                            <th>Target</th>
                            <th>Stop Loss</th>
                            <th>RR</th>
                            <th>Explanation</th>
                        </tr>
                    </thead>

                    <tbody>
                        {{TABLE_ROWS}}
                    </tbody>
                </table>
            </div>
        </section>

        <p class="footer">
            Disclaimer: This dashboard is for educational and research purposes only. It is not financial advice or a recommendation.
            Always verify chart structure, market trend, liquidity, volume quality, event risk, and your own risk limits before trading.
        </p>
    </main>
</body>
</html>
"""

    html_output = template
    html_output = html_output.replace("{{GENERATED_TIME}}", esc(generated_time))
    html_output = html_output.replace("{{TOTAL_CANDIDATES}}", esc(total_candidates))
    html_output = html_output.replace("{{HIGHEST_COUNT}}", esc(highest_count))
    html_output = html_output.replace("{{MEDIUM_COUNT}}", esc(medium_count))
    html_output = html_output.replace("{{LOW_COUNT}}", esc(low_count))
    html_output = html_output.replace("{{BEST_SCORE}}", esc(best_score))
    html_output = html_output.replace("{{AVG_RR}}", esc(avg_rr))
    html_output = html_output.replace("{{BIAS}}", esc(bias))
    html_output = html_output.replace("{{BIAS_TEXT}}", esc(bias_text))
    html_output = html_output.replace("{{SETUP_CARDS}}", setup_cards)
    html_output = html_output.replace("{{TABLE_ROWS}}", table_rows)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_output)

    print(f"Dashboard report created: {OUTPUT_HTML}")
    print(f"Generated timestamp: {generated_time}")
    print(f"Total candidates displayed: {total_candidates}")


if __name__ == "__main__":
    generate_html()
