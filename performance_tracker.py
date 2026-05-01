import pandas as pd
from datetime import datetime
import os

SCANNER_FILE = "scanner_output.csv"
LOG_FILE = "trade_log.csv"

today = datetime.now().strftime("%Y-%m-%d")

# ---------------- LOAD TODAY'S SCANNER ----------------

if not os.path.exists(SCANNER_FILE):
    print("scanner_output.csv not found. Run scanner.py first.")
    exit()

scanner = pd.read_csv(SCANNER_FILE)

if scanner.empty:
    print("No scanner candidates today. Nothing added to trade log.")
    exit()

# Sort by conviction and pick top 3
scanner = scanner.sort_values(by="Conviction Score", ascending=False).head(3)

# ---------------- CREATE TODAY'S LOG ENTRIES ----------------

new_entries = []

for rank, (_, row) in enumerate(scanner.iterrows(), start=1):
    new_entries.append({
        "Signal Date": today,
        "Rank": rank,
        "Symbol": row.get("Symbol", ""),
        "Signal": row.get("Signal", ""),
        "Conviction Score": row.get("Conviction Score", ""),
        "Grade": row.get("Grade", ""),
        "Entry Trigger": row.get("Entry Trigger", ""),
        "Stop Loss": row.get("Stop Loss", ""),
        "Target": row.get("Target", ""),
        "Risk/Reward": row.get("Risk/Reward", ""),
        "Status": "Pending Trigger",
        "Triggered Date": "",
        "Exit Date": "",
        "Exit Price": "",
        "Result": "",
        "R Multiple": "",
        "Days Tracked": 0,
        "Notes": "Top 3 scanner pick"
    })

new_df = pd.DataFrame(new_entries)

# ---------------- LOAD EXISTING LOG ----------------

if os.path.exists(LOG_FILE):
    log = pd.read_csv(LOG_FILE)
else:
    log = pd.DataFrame()

# ---------------- AVOID DUPLICATES ----------------

if not log.empty:
    existing_keys = set(
        log["Signal Date"].astype(str) + "|" +
        log["Symbol"].astype(str) + "|" +
        log["Signal"].astype(str)
    )

    new_df["key"] = (
        new_df["Signal Date"].astype(str) + "|" +
        new_df["Symbol"].astype(str) + "|" +
        new_df["Signal"].astype(str)
    )

    new_df = new_df[~new_df["key"].isin(existing_keys)]
    new_df = new_df.drop(columns=["key"])

# ---------------- SAVE UPDATED LOG ----------------

if log.empty:
    updated_log = new_df
else:
    updated_log = pd.concat([new_df, log], ignore_index=True)

updated_log.to_csv(LOG_FILE, index=False)

print(f"Added {len(new_df)} new Top 3 trade ideas to trade_log.csv")
print(f"Total logged trade ideas: {len(updated_log)}")