import pandas as pd
from datetime import datetime

df = pd.read_csv("scanner_output.csv")

if df.empty:
    html_rows = "<tr><td colspan='11'>No watchlist candidates found today.</td></tr>"
else:
    html_rows = ""
    for _, row in df.iterrows():
        signal_class = "buy" if "BUY" in row["Signal"] else "sell"

        html_rows += f"""
        <tr>
            <td><strong>{row['Symbol']}</strong></td>
            <td class="{signal_class}">{row['Signal']}</td>
            <td>{row['Close']}</td>
            <td>{row['Entry Trigger']}</td>
            <td>{row['Stop Loss']}</td>
            <td>{row['Target']}</td>
            <td>{row['Change%']}%</td>
            <td>{row['Volume Ratio']}</td>
            <td>{row['Score']}</td>
            <td>
                Stock is near breakout/breakdown.  
                Trade only if it crosses the entry trigger.
            </td>
        </tr>
        """

html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Swing Trading Scanner</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #f4f6f8;
            margin: 0;
            padding: 30px;
            color: #222;
        }}

        .container {{
            max-width: 1200px;
            margin: auto;
        }}

        h1 {{
            color: #111827;
            margin-bottom: 5px;
        }}

        .subtitle {{
            color: #6b7280;
            margin-bottom: 25px;
        }}

        .cards {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 25px;
        }}

        .card {{
            background: white;
            padding: 18px;
            border-radius: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        .card h3 {{
            margin: 0 0 8px;
            font-size: 15px;
            color: #374151;
        }}

        .card p {{
            margin: 0;
            font-size: 22px;
            font-weight: bold;
        }}

        .explain {{
            background: #fff7ed;
            border-left: 5px solid #f97316;
            padding: 18px;
            border-radius: 12px;
            margin-bottom: 25px;
            line-height: 1.6;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}

        th {{
            background: #111827;
            color: white;
            padding: 12px;
            text-align: left;
            font-size: 13px;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
            font-size: 13px;
        }}

        tr:hover {{
            background: #f9fafb;
        }}

        .buy {{
            color: #047857;
            font-weight: bold;
        }}

        .sell {{
            color: #b91c1c;
            font-weight: bold;
        }}

        .footer {{
            margin-top: 25px;
            color: #6b7280;
            font-size: 13px;
        }}
    </style>
</head>
<body>
<div class="container">

    <h1>📈 Swing Trading Scanner Report</h1>
    <p class="subtitle">Generated on {datetime.now().strftime('%d %B %Y, %I:%M %p')}</p>

    <div class="cards">
        <div class="card">
            <h3>Total Candidates</h3>
            <p>{len(df)}</p>
        </div>
        <div class="card">
            <h3>BUY Watchlist</h3>
            <p>{len(df[df['Signal'].str.contains('BUY', na=False)]) if not df.empty else 0}</p>
        </div>
        <div class="card">
            <h3>SELL Watchlist</h3>
            <p>{len(df[df['Signal'].str.contains('SELL', na=False)]) if not df.empty else 0}</p>
        </div>
        <div class="card">
            <h3>Best Score</h3>
            <p>{df['Score'].max() if not df.empty else 0}</p>
        </div>
    </div>

    <div class="explain">
        <strong>How to read this report:</strong><br>
        A stock in the BUY watchlist is near a breakout.  
        If it crosses the <strong>Entry Trigger</strong>, it becomes a valid trade candidate.  
        The <strong>Stop Loss</strong> is your risk control level.  
        The <strong>Target</strong> is the expected reward area.  
        The <strong>Score</strong> ranks the quality of the setup — higher is better.
    </div>

    <table>
        <tr>
            <th>Stock</th>
            <th>Signal</th>
            <th>Close</th>
            <th>Entry Trigger</th>
            <th>Stop Loss</th>
            <th>Target</th>
            <th>Change %</th>
            <th>Volume Ratio</th>
            <th>Score</th>
            <th>Explanation</th>
        </tr>
        {html_rows}
    </table>

    <p class="footer">
        Educational scanner only. Not financial advice. Always verify chart structure and market conditions before trading.
    </p>

</div>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Beautiful report created: index.html")