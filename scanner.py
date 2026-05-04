import pandas as pd
import yfinance as yf
import ta

# ---------------- CONFIG ----------------

MIN_AVG_TURNOVER = 200000000      # ₹20 crore approx
MIN_RR = 2.5
MIN_CONVICTION = 75
MAX_RESULTS = 12

symbols = pd.read_csv("symbols.csv")["symbol"].dropna().unique().tolist()
results = []

print("Scanning NIFTY 500 with high-conviction swing-trading filters...")

# ---------------- HELPER FUNCTIONS ----------------

def flatten_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def safe_download(symbol, period="1y"):
    df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=False)
    df = flatten_columns(df)
    return df

def compute_score(
    signal,
    close,
    ema20,
    ema50,
    ema200,
    rsi,
    volume_ratio,
    relative_strength,
    rr,
    atr_pct,
    distance_to_trigger
):
    score = 0

    # 1. Trend quality — 20 points
    if signal == "BUY":
        if close > ema20 > ema50 > ema200:
            score += 20
        elif close > ema20 > ema50:
            score += 14
    else:
        if close < ema20 < ema50:
            score += 18
        elif close < ema20:
            score += 12

    # 2. Relative strength — 20 points
    if signal == "BUY":
        if relative_strength >= 8:
            score += 20
        elif relative_strength >= 5:
            score += 16
        elif relative_strength >= 2:
            score += 12
    else:
        if relative_strength <= -8:
            score += 20
        elif relative_strength <= -5:
            score += 16
        elif relative_strength <= -2:
            score += 12

    # 3. Volume confirmation — 15 points
    if volume_ratio >= 2:
        score += 15
    elif volume_ratio >= 1.5:
        score += 12
    elif volume_ratio >= 1:
        score += 8

    # 4. Momentum quality — 15 points
    if signal == "BUY":
        if 55 <= rsi <= 64:
            score += 15
        elif 52 <= rsi < 55 or 64 < rsi <= 68:
            score += 10
    else:
        if 36 <= rsi <= 45:
            score += 15
        elif 32 <= rsi < 36 or 45 < rsi <= 48:
            score += 10

    # 5. Risk/reward — 15 points
    if rr >= 4:
        score += 15
    elif rr >= 3:
        score += 12
    elif rr >= 2.5:
        score += 8

    # 6. Volatility quality — 10 points
    if 1.5 <= atr_pct <= 4:
        score += 10
    elif 1 <= atr_pct < 1.5 or 4 < atr_pct <= 5.5:
        score += 6

    # 7. Entry proximity — 5 points
    if distance_to_trigger <= 0.5:
        score += 5
    elif distance_to_trigger <= 1:
        score += 3
    elif distance_to_trigger <= 1.5:
        score += 1

    return min(score, 100)

# ---------------- NIFTY BENCHMARK ----------------

nifty = safe_download("^NSEI", period="6mo")

if nifty.empty or len(nifty) < 30:
    print("Could not load NIFTY data.")
    exit()

nifty_close = nifty["Close"]
nifty_return_20 = ((nifty_close.iloc[-1] - nifty_close.iloc[-21]) / nifty_close.iloc[-21]) * 100

# ---------------- STOCK SCAN ----------------

for symbol in symbols:
    try:
        df = safe_download(symbol, period="1y")

        if df.empty or len(df) < 220:
            continue

        df = df.dropna()

        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        df["EMA200"] = df["Close"].ewm(span=200).mean()
        df["RSI"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
        df["ATR"] = ta.volatility.AverageTrueRange(
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            window=14
        ).average_true_range()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        close = latest["Close"]
        prev_high = prev["High"]
        prev_low = prev["Low"]

        ema20 = latest["EMA20"]
        ema50 = latest["EMA50"]
        ema200 = latest["EMA200"]
        rsi = latest["RSI"]
        atr = latest["ATR"]

        volume = latest["Volume"]
        avg_volume_20 = df["Volume"].tail(20).mean()
        volume_ratio = volume / avg_volume_20 if avg_volume_20 > 0 else 0

        avg_turnover = (df["Close"] * df["Volume"]).tail(20).mean()

        stock_return_20 = ((close - df["Close"].iloc[-21]) / df["Close"].iloc[-21]) * 100
        relative_strength = stock_return_20 - nifty_return_20

        atr_pct = (atr / close) * 100

        # Avoid illiquid stocks
        if avg_turnover < MIN_AVG_TURNOVER:
            continue

        signal = None
        entry = None
        stop = None
        target = None
        rr = None
        distance_to_trigger = None
        setup_reason = ""

        # ---------------- BUY SETUP ----------------
        if (
            close > ema20 > ema50 > ema200
            and 52 <= rsi <= 68
            and relative_strength >= 2
            and volume_ratio >= 1
            and 1 <= atr_pct <= 5.5
        ):
            entry = prev_high
            distance_to_trigger = abs((entry - close) / close) * 100

            if distance_to_trigger <= 1.5:
                stop = entry - (1.5 * atr)
                risk = entry - stop
                target = entry + (2.5 * risk)
                rr = (target - entry) / risk

                if rr >= MIN_RR:
                    signal = "BUY"
                    setup_reason = (
                        "High-conviction bullish setup: uptrend, relative strength versus NIFTY, "
                        "acceptable volume, controlled volatility, and close to breakout trigger."
                    )

        # ---------------- SELL SETUP ----------------
        elif (
            close < ema20 < ema50
            and 32 <= rsi <= 48
            and relative_strength <= -2
            and volume_ratio >= 1
            and 1 <= atr_pct <= 6
        ):
            entry = prev_low
            distance_to_trigger = abs((close - entry) / close) * 100

            if distance_to_trigger <= 1.5:
                stop = entry + (1.5 * atr)
                risk = stop - entry
                target = entry - (2.5 * risk)
                rr = (entry - target) / risk

                if rr >= MIN_RR:
                    signal = "SELL"
                    setup_reason = (
                        "High-conviction bearish setup: downtrend, weak relative strength versus NIFTY, "
                        "acceptable volume, controlled volatility, and close to breakdown trigger."
                    )

        if signal is None:
            continue

        conviction = compute_score(
            signal=signal,
            close=close,
            ema20=ema20,
            ema50=ema50,
            ema200=ema200,
            rsi=rsi,
            volume_ratio=volume_ratio,
            relative_strength=relative_strength,
            rr=rr,
            atr_pct=atr_pct,
            distance_to_trigger=distance_to_trigger
        )

        if conviction < MIN_CONVICTION:
            continue

        if conviction >= 85:
            grade = "A"
        elif conviction >= 75:
            grade = "B+"
        else:
            grade = "Avoid"

        results.append({
            "Symbol": symbol,
            "Signal": signal,
            "Conviction Score": round(conviction, 1),
            "Grade": grade,
            "Close": round(close, 2),
            "Entry Trigger": round(entry, 2),
            "Stop Loss": round(stop, 2),
            "Target": round(target, 2),
            "Risk/Reward": round(rr, 2),
            "RSI": round(rsi, 1),
            "ATR%": round(atr_pct, 2),
            "Volume Ratio": round(volume_ratio, 2),
            "Relative Strength vs NIFTY": round(relative_strength, 2),
            "Distance to Trigger%": round(distance_to_trigger, 2),
            "Suggested Action": "ENTER ONLY IF TRIGGER BREAKS",
            "Avoid If": "Avoid if price opens far beyond trigger, volume is weak, or market index is sharply against the trade.",
            "Explanation": setup_reason
        })

    except Exception:
        continue

# ---------------- OUTPUT ----------------

# ---------------- OUTPUT ----------------

from pathlib import Path

OUTPUT_FILE = "scanner_output.csv"
output = pd.DataFrame(results)

if not output.empty:
    output = output.sort_values(by="Conviction Score", ascending=False).head(MAX_RESULTS)

    print("\nHigh-Conviction Watchlist:")
    print(output)

    output.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved fresh high-conviction results to {OUTPUT_FILE}")

else:
    print("\nNo fresh high-conviction candidates found in this run.")

    keep_existing = False

    if Path(OUTPUT_FILE).exists():
        try:
            previous_output = pd.read_csv(OUTPUT_FILE)
            if not previous_output.empty:
                keep_existing = True
        except Exception:
            keep_existing = False

    if keep_existing:
        print(f"Keeping previous valid {OUTPUT_FILE} instead of overwriting it with a blank file.")
    else:
        print(f"No previous valid {OUTPUT_FILE} found. Creating an empty file with expected columns.")

        empty_columns = [
            "Symbol",
            "Signal",
            "Conviction Score",
            "Grade",
            "Close",
            "Entry Trigger",
            "Stop Loss",
            "Target",
            "Risk/Reward",
            "RSI",
            "ATR%",
            "Volume Ratio",
            "Relative Strength vs NIFTY",
            "Distance to Trigger%",
            "Suggested Action",
            "Avoid If",
            "Explanation"
        ]

        pd.DataFrame(columns=empty_columns).to_csv(OUTPUT_FILE, index=False)
