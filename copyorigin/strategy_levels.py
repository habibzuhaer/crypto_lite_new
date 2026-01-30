#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# strategy_levels.py — расчёт уровней X,F,f1,A,a1,C,c1,D,Y
# Ровный шаг по базовой свече (тело+тень в сторону движения).
# Печати/тестовых блоков нет. Только функции для импорта.

from typing import Dict, List, Optional

# -------------------- НОРМАЛИЗАЦИЯ --------------------

def _norm(c: Dict) -> Dict[str, float]:
    """Нормализуем ключи и приводим к float."""
    return {
        "ts": int(c.get("ts") or c.get("timestamp") or 0),
        "open": float(c.get("open") or c.get("o") or 0.0),
        "high": float(c.get("high") or c.get("h") or 0.0),
        "low":  float(c.get("low")  or c.get("l") or 0.0),
        "close":float(c.get("close")or c.get("c") or 0.0),
    }

def _is_green(c: Dict) -> bool:
    """Зелёная, если close >= open."""
    c = _norm(c)
    return c["close"] >= c["open"]

def _impulse_size(c: Dict) -> float:
    """
    Импульс базовой: тело + тень В СТОРОНУ движения.
    - зелёная: high - open
    - красная: open - low
    """
    c = _norm(c)
    return (c["high"] - c["open"]) if _is_green(c) else (c["open"] - c["low"])

# -------------------- ВЫБОР БАЗОВОЙ СВЕЧИ --------------------

def pick_biggest_candle(candles: List[Dict]) -> Optional[Dict]:
    """
    Возвращает свечу с максимальным импульсом по правилу выше.
    Формат возвращаемой свечи: {ts, open, high, low, close} float (ts=int).
    """
    if not candles:
        return None
    best = None
    best_sz = -1.0
    for raw in candles:
        sz = _impulse_size(raw)
        if sz > best_sz:
            best = raw
            best_sz = sz
    return _norm(best) if best else None

# -------------------- РАСЧЁТ УРОВНЕЙ --------------------

def calculate_levels_for_candle(base: Dict) -> Dict[str, float]:
    """
    Ровный шаг Δ = |C - A|. Жёсткий порядок уровней:
    X, F, f1, A, a1, C, c1, D, Y
    """
    b = _norm(base)
    A = b["open"]

    if _is_green(b):
        C = b["high"]
        d = C - A
        F = A - d
        D = C + d
        X = F - d
        Y = D + d
    else:
        C = b["low"]
        d = A - C
        F = A + d
        D = C - d
        X = F + d
        Y = D - d

    f1 = 0.5 * (F + A)
    a1 = 0.5 * (A + C)
    c1 = 0.5 * (C + D)

    out: Dict[str, float] = {}
    out["X"]  = float(X)
    out["F"]  = float(F)
    out["f1"] = float(f1)
    out["A"]  = float(A)
    out["a1"] = float(a1)
    out["C"]  = float(C)
    out["c1"] = float(c1)
    out["D"]  = float(D)
    out["Y"]  = float(Y)
    return out

# -------------------- ОСНОВНАЯ ФУНКЦИЯ --------------------

def calculate_levels(
    candles: List[Dict],
    symbol: Optional[str] = None,
    tf: Optional[str] = None,
    use_biggest_from_last: Optional[int] = None,
) -> Dict[str, float]:
    """
    Обёртка для проекта.

    use_biggest_from_last:
        None / 0  — искать базовую во всём массиве
        int > 0   — искать базовую в candles[-N:]
    """
    if not candles:
        return {}

    src = candles
    if isinstance(use_biggest_from_last, int) and use_biggest_from_last > 0:
        src = candles[-use_biggest_from_last:]

    base = pick_biggest_candle(src)
    if not base:
        return {}

    levels = calculate_levels_for_candle(base)
    levels["_base_ts"] = base["ts"]
    return levels

# -------------------- EXPORT --------------------

__all__ = [
    "pick_biggest_candle",
    "calculate_levels_for_candle",
    "calculate_levels",
]
