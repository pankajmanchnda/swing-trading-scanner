import pandas as pd
import yfinance as yf

symbols = pd.read_csv("symbols.csv")["symbol"].dropna().unique().tolist()
results = []

print("Scanning NIFTY 500 for next-day watchlist...")

for symbol in symbols:
    try:
        df = yf.download(symbol, period="6mo", interval="1d", progress=False, auto_adjust=False)

        if df.empty or len(df) < 60:
            continue

        df = df.dropna()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        close = latest["Close"]
        high = latest["High"]
        low = latest["Low"]
        prev_high = prev["High"]
        prev_low = prev["Low"]
        prev_close = prev["Close"]
        volume = latest["Volume"]

        if hasattr(close, "iloc"):
            close = close.iloc[0]
            high = high.iloc[0]
            low = low.iloc[0]
            prev_high = prev_high.iloc[0]
            prev_low = prev_low.iloc[0]
            prev_close = prev_close.iloc[0]
            volume = volume.iloc[0]

        close = float(close)
        high = float(high)
        low = float(low)
        prev_high = float(prev_high)
        prev_low = float(prev_low)
        prev_close = float(prev_close)
        volume = float(volume)

        avg_volume = df["Volume"].tail(20).mean()
        if hasattr(avg_volume, "iloc"):
            avg_volume = avg_volume.iloc[0]
        avg_volume = float(avg_volume)

        change_pct = ((close - prev_close) / prev_close) * 100
        volume_ratio = volume / avg_volume if avg_volume > 0 else 0

        distance_to_breakout = ((prev_high - close) / close) * 100
        distance_to_breakdown = ((close - prev_low) / close) * 100

        signal = None
        entry = None
        stop_loss = None
        target = None
        score = 0

        if close >= prev_high * 0.98:
            signal = "BUY WATCHLIST"
            entry = prev_high
            stop_loss = prev_low
            risk = entry - stop_loss
            target = entry + (risk * 2)

            score += max(0, 5 - abs(distance_to_breakout))
            if change_pct > 0:
                score += 1
            if volume_ratio > 1:
                score += 2

        elif close <= prev_low * 1.02:
            signal = "SELL WATCHLIST"
            entry = prev_low
            stop_loss = prev_high
            risk = stop_loss - entry
            target = entry - (risk * 2)

            score += max(0, 5 - abs(distance_to_breakdown))
            if change_pct < 0:
                score += 1
            if volume_ratio > 1:
                score += 2

        if signal:
            results.append({
                "Symbol": symbol,
                "Signal": signal,
                "Close": round(close, 2),
                "Entry Trigger": round(entry, 2),
                "Stop Loss": round(stop_loss, 2),
                "Target": round(target, 2),
                "Change%": round(change_pct, 2),
                "Volume Ratio": round(volume_ratio, 2),
                "Distance to Breakout%": round(distance_to_breakout, 2),
                "Distance to Breakdown%": round(distance_to_breakdown, 2),
                "Score": round(score, 2)
            })

    except Exception as e:
        print(symbol, "ERROR:", e)

output = pd.DataFrame(results)

if not output.empty:
    output = output.sort_values(by="Score", ascending=False).head(20)

print("\nTop 20 Watchlist:")
print(output)

output.to_csv("scanner_output.csv", index=False)

print("\nSaved to scanner_output.csv")