import pandas as pd
import re
from pathlib import Path

INDEX_FILE = "index.html"
LOG_FILE = "trade_log.csv"

index_path = Path(INDEX_FILE)

if not index_path.exists():
    print("index.html not found. Run generate_report.py first.")
    exit()

try:
    trade_log = pd.read_csv(LOG_FILE)
except FileNotFoundError:
    trade_log = pd.DataFrame()

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

def signal_class(signal):
    s = str(signal).upper()
    if "BUY" in s:
        return "buy"
    if "SELL" in s:
        return "sell"
    return "neutral"

def build_trade_log_tabs(trade_log):
    if trade_log.empty:
        return """
        <div class="performance-empty">
            No performance history yet. Run performance_tracker.py after scanner.py to start logging Top 3 picks.
        </div>
        """

    trade_log = trade_log.copy()

    if "Signal Date" in trade_log.columns:
        trade_log["Signal Date"] = trade_log["Signal Date"].astype(str)
        trade_log = trade_log.sort_values(by="Signal Date", ascending=False)

    chunks = [trade_log.iloc[i:i + 60] for i in range(0, len(trade_log), 60)]

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
        <button class="perf-tab-button {active_class}" onclick="showPerfTab('{tab_id}', this)">
            {label}
        </button>
        """

        rows = ""

        for _, row in chunk.iterrows():
            status = row.get("Status", "-")
            signal = row.get("Signal", "-")

            rows += f"""
            <tr>
                <td>{row.get("Signal Date", "-")}</td>
                <td>{row.get("Rank", "-")}</td>
                <td class="stock">{row.get("Symbol", "-")}</td>
                <td><span class="badge {signal_class(signal)}">{signal}</span></td>
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
        <div id="{tab_id}" class="perf-tab-panel" style="display:{display_style};">
            <div class="performance-table-wrap">
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
    <div class="perf-tabs">
        <div class="perf-tab-buttons">
            {buttons}
        </div>
        {panels}
    </div>
    """

performance_html = build_trade_log_tabs(trade_log)

performance_section = f"""
<!-- PERFORMANCE_LOG_START -->
<style>
.performance-section {{
    margin-top: 28px;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 18px;
    padding: 22px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}}

.performance-section h2 {{
    margin: 0 0 6px;
    font-size: 26px;
}}

.performance-section .section-note {{
    color: #6b7280;
    margin: 0 0 16px;
    font-size: 14px;
}}

.perf-tab-buttons {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 14px;
}}

.perf-tab-button {{
    border: 1px solid #e5e7eb;
    background: white;
    color: #374151;
    padding: 9px 14px;
    border-radius: 999px;
    font-weight: 800;
    cursor: pointer;
}}

.perf-tab-button.active {{
    background: #111827;
    color: white;
}}

.performance-table-wrap {{
    overflow-x: auto;
    border-radius: 14px;
    border: 1px solid #e5e7eb;
}}

.performance-table-wrap table {{
    width: 100%;
    min-width: 1200px;
    border-collapse: collapse;
}}

.performance-table-wrap th {{
    background: #111827;
    color: white;
    text-align: left;
    padding: 10px;
    font-size: 12px;
    white-space: nowrap;
}}

.performance-table-wrap td {{
    padding: 9px 10px;
    border-bottom: 1px solid #e5e7eb;
    font-size: 12.5px;
    white-space: nowrap;
}}

.status-pill {{
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
}}

.status-win {{
    background: #d1fae5;
    color: #047857;
}}

.status-loss {{
    background: #fee2e2;
    color: #b91c1c;
}}

.status-triggered {{
    background: #dbeafe;
    color: #1d4ed8;
}}

.status-pending {{
    background: #fef3c7;
    color: #a16207;
}}

.status-expired {{
    background: #e5e7eb;
    color: #374151;
}}

.status-gap {{
    background: #ffedd5;
    color: #c2410c;
}}

.status-neutral {{
    background: #f3f4f6;
    color: #374151;
}}

.performance-empty {{
    padding: 24px;
    color: #6b7280;
    background: #f9fafb;
    border-radius: 14px;
    border: 1px solid #e5e7eb;
}}
</style>

<section class="performance-section">
    <h2>📊 Top 3 Performance Log</h2>
    <p class="section-note">
        Tracks the platform's Top 3 daily picks. Latest 60 ideas are shown first; older records appear in 60-trade tabs.
    </p>
    {performance_html}
</section>

<script>
function showPerfTab(tabId, button) {{
    const panels = document.querySelectorAll('.perf-tab-panel');
    const buttons = document.querySelectorAll('.perf-tab-button');

    panels.forEach(panel => {{
        panel.style.display = 'none';
    }});

    buttons.forEach(btn => {{
        btn.classList.remove('active');
    }});

    document.getElementById(tabId).style.display = 'block';
    button.classList.add('active');
}}
</script>
<!-- PERFORMANCE_LOG_END -->
"""

html = index_path.read_text(encoding="utf-8")

# Remove old performance section if already inserted
html = re.sub(
    r"<!-- PERFORMANCE_LOG_START -->.*?<!-- PERFORMANCE_LOG_END -->",
    "",
    html,
    flags=re.DOTALL
)

# Insert before footer if possible, otherwise before closing body
if '<p class="footer">' in html:
    html = html.replace('<p class="footer">', performance_section + '\n<p class="footer">')
elif "</body>" in html:
    html = html.replace("</body>", performance_section + "\n</body>")
else:
    html += performance_section

index_path.write_text(html, encoding="utf-8")

print("Performance section added to index.html")