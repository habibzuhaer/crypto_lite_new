import numpy as np
from typing import List, Dict, Optional
from strategy_levels import calculate_rsi

def analyze_trend(candles: List[Dict], candles_higher: List[Dict], rsi_period: int = 14, lookback: int = 35):
    if len(candles) < lookback or len(candles_higher) == 0:
        return None

    closes = np.array([float(c.get("close", 0)) for c in candles[-lookback:]])
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

    # Используем RSI из strategy_levels
    rsi = calculate_rsi(candles, rsi_period)

    # Подтверждение по старшему ТФ
    if candles_higher:
        high_c = candles_higher[-1]
        htf_bull = float(high_c.get("close", 0)) > float(high_c.get("open", 0))
    else:
        htf_bull = False

    # Определяем тренд
    if trend_dir == 1 and htf_bull:
        trend = "long"
    elif trend_dir == -1 and not htf_bull:
        trend = "short"
    else:
        trend = "neutral"
    
    conf = min(1.0, trend_len / 5)

    return {"trend": trend, "confidence": conf, "rsi": rsi}