def scan_stock(symbol):
    try:
        df = yf.download(symbol, period="3mo", interval="1d", progress=False)

        if df.empty or len(df) < 20:
            return None

        df = df.dropna()

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(latest["Close"])
        prev_high = float(prev["High"])
        prev_low = float(prev["Low"])

        change_pct = ((close - float(prev["Close"])) / float(prev["Close"])) * 100

        # Relaxed conditions
        if close > prev_high * 0.995:  # near breakout
            return {
                "Symbol": symbol,
                "Signal": "BUY",
                "Entry": round(close, 2),
                "Change%": round(change_pct, 2)
            }

        if close < prev_low * 1.005:  # near breakdown
            return {
                "Symbol": symbol,
                "Signal": "SELL",
                "Entry": round(close, 2),
                "Change%": round(change_pct, 2)
            }

    except:
        return None

    return None