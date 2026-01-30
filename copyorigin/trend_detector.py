import numpy as np

def analyze_trend(candles, candles_higher, rsi_period=14, lookback=35):
    if len(candles) < lookback or len(candles_higher) == 0:
        return None

    closes = np.array([float(c["close"]) for c in candles[-lookback:]])
    direction = np.sign(closes[1:] - closes[:-1])
    trend_len = 0
    trend_dir = 0

    for i in range(len(direction) - 3, -1, -1):
        seq = direction[i:i + 3]
        if np.all(seq > 0):
            trend_dir = 1
            trend_len += 1
        elif np.all(seq < 0):
            trend_dir = -1
            trend_len += 1
        else:
            if trend_len > 0:
                break

    if trend_len < 1:
        return {"trend": "neutral", "confidence": 0.0, "rsi": None}

    # RSI
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = sum(gains[:rsi_period]) / rsi_period
    avg_loss = sum(losses[:rsi_period]) / rsi_period
    for i in range(rsi_period, len(gains)):
        avg_gain = (avg_gain * (rsi_period - 1) + gains[i]) / rsi_period
        avg_loss = (avg_loss * (rsi_period - 1) + losses[i]) / rsi_period
    rsi = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))

    # Подтверждение по старшему ТФ
    high_c = candles_higher[-1]
    htf_bull = float(high_c["close"]) > float(high_c["open"])

    trend = "long" if trend_dir == 1 and htf_bull else "short" if trend_dir == -1 and not htf_bull else "neutral"
    conf = min(1.0, trend_len / 5)

    return {"trend": trend, "confidence": conf, "rsi": rsi}
