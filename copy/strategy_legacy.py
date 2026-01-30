# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Any, Optional

# ───────────────────────────────
# RSI(14)
# ───────────────────────────────
def rsi_value(candles: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    closes = [float(c.get("close", 0.0)) for c in candles]
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

# ───────────────────────────────
# ПАТТЕРНЫ (Engulfing)
# ───────────────────────────────
def detect_patterns(candles: List[Dict[str, Any]], lookback: int = 96) -> List[str]:
    out: List[str] = []
    if len(candles) < 2:
        return out
    rng = candles[-min(lookback, len(candles)):]
    for i in range(1, len(rng)):
        p, c = rng[i - 1], rng[i]
        po, pc = float(p["open"]), float(p["close"])
        co, cc = float(c["open"]), float(c["close"])
        if pc < po and cc > co and co <= pc and cc >= po:
            out.append("Bullish Engulfing")
            break
        if pc > po and cc < co and co >= pc and cc <= po:
            out.append("Bearish Engulfing")
            break
    return out

# ───────────────────────────────
# УРОВНИ X–F–A–C–D–Y (твоя логика)
# ───────────────────────────────
def calculate_levels(
    candles: List[Dict[str, Any]],
    symbol: str,
    tf: str,
    use_biggest_from_last: int | None = 240
) -> Dict[str, float]:
    if not candles:
        return {"X": 0.0, "F": 0.0, "A": 0.0, "C": 0.0, "D": 0.0, "Y": 0.0, "src_ts": 0}

    src = candles[-1]
    if isinstance(use_biggest_from_last, int) and use_biggest_from_last > 1:
        chunk = candles[-min(use_biggest_from_last, len(candles)):]
        src = max(
            chunk,
            key=lambda c: abs(float(c.get("close", 0.0)) - float(c.get("open", 0.0)))
        )

    o = float(src.get("open", 0.0))
    h = float(src.get("high", 0.0))
    l = float(src.get("low", 0.0))
    cl = float(src.get("close", 0.0))
    ts = int(src.get("ts", 0))

    is_green = cl >= o
    A = o
    C = h if is_green else l
    H = abs(C - A) or max(abs(h - l), 1e-9)
    dir_ = 1.0 if (C - A) >= 0 else -1.0

    X = C + 2.0 * dir_ * H
    F = A - 1.0 * dir_ * H
    D = C + 1.0 * dir_ * H
    Y = A - 2.0 * dir_ * H

    return {"X": X, "F": F, "A": A, "C": C, "D": D, "Y": Y, "src_ts": ts}
