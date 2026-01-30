#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# strategy_levels.py — расчёт уровней X,F,f1,A,a1,C,c1,D,Y
# Ровный шаг по базовой свече (тело+тень в сторону движения).
# Печати/тестовых блоков нет. Только функции для импорта.

from typing import Dict, List, Optional, Union, Tuple
import numpy as np

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

# -------------------- RSI РАСЧЁТ --------------------

def calculate_rsi(candles: List[Dict], period: int = 14) -> Optional[float]:
    """Вычисляет RSI(14) для последней свечи в массиве."""
    if len(candles) < period + 1:
        return None
    
    closes = []
    for c in candles:
        norm_c = _norm(c)
        closes.append(norm_c["close"])
    
    if len(closes) < period + 1:
        return None
    
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def rsi_series(candles: List[Dict], period: int = 14) -> List[Optional[float]]:
    """Возвращает RSI для каждой позиции (первые period значений = None)."""
    if len(candles) < period + 1:
        return [None] * len(candles)
    
    closes = []
    for c in candles:
        norm_c = _norm(c)
        closes.append(norm_c["close"])
    
    rsis = [None] * period
    for i in range(period, len(closes)):
        gains, losses = [], []
        for j in range(i - period + 1, i + 1):
            change = closes[j] - closes[j - 1]
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        rsis.append(rsi)
    
    return rsis

# -------------------- EMA РАСЧЁТ (ИСПРАВЛЕННЫЙ) --------------------

def calculate_ema_series(candles: List[Dict], period: int) -> List[Optional[float]]:
    """Вычисляет EMA для каждого бара (по ценам закрытия)."""
    if len(candles) < period:
        return [None] * len(candles)
    
    closes = []
    for c in candles:
        norm_c = _norm(c)
        closes.append(norm_c["close"])
    
    # Рассчитываем EMA для каждого бара
    emas = [None] * (period - 1)  # Первые period-1 значений = None
    
    # Начальное значение EMA - SMA
    sma = sum(closes[:period]) / period
    emas.append(sma)
    
    # Коэффициент сглаживания
    k = 2.0 / (period + 1.0)
    
    # Вычисляем EMA для остальных баров
    for i in range(period, len(closes)):
        ema = (closes[i] * k) + (emas[-1] * (1 - k))
        emas.append(ema)
    
    return emas

def calculate_ema(candles: List[Dict], period: int) -> Optional[float]:
    """Вычисляет EMA для последнего бара."""
    emas = calculate_ema_series(candles, period)
    return emas[-1] if emas else None

def calculate_all_emas(candles: List[Dict]) -> Dict[str, Optional[float]]:
    """Вычисляет EMA-8, EMA-54, EMA-78, EMA-200 для последнего бара."""
    periods = [8, 54, 78, 200]
    result = {}
    
    for period in periods:
        ema_value = calculate_ema(candles, period)
        result[f"EMA_{period}"] = ema_value
    
    return result

def get_all_ema_series(candles: List[Dict]) -> Dict[str, List[Optional[float]]]:
    """Возвращает серии EMA для всех периодов."""
    periods = [8, 54, 78, 200]
    result = {}
    
    for period in periods:
        ema_series = calculate_ema_series(candles, period)
        result[f"EMA_{period}"] = ema_series
    
    return result

def ema_trend_analysis(emas: Dict[str, Optional[float]], current_price: float) -> Dict[str, any]:
    """Анализ тренда на основе EMA."""
    # Проверяем, что все EMA рассчитаны
    for key in ["EMA_8", "EMA_54", "EMA_78", "EMA_200"]:
        if emas.get(key) is None:
            return {"trend": "неопределён", "strength": 0, "details": "Недостаточно данных"}
    
    ema8 = emas["EMA_8"]
    ema54 = emas["EMA_54"]
    ema78 = emas["EMA_78"]
    ema200 = emas["EMA_200"]
    
    # Определяем положение цены относительно EMA
    above_ema8 = current_price > ema8
    above_ema54 = current_price > ema54
    above_ema78 = current_price > ema78
    above_ema200 = current_price > ema200
    
    # Определяем порядок EMA (бычий: EMA_8 > EMA_54 > EMA_78 > EMA_200)
    bullish_order = ema8 > ema54 > ema78 > ema200
    bearish_order = ema8 < ema54 < ema78 < ema200
    
    # Определяем тренд
    if bullish_order and above_ema8:
        trend = "сильный бычий"
        strength = 100
    elif bearish_order and not above_ema8:
        trend = "сильный медвежий"
        strength = 100
    elif ema8 > ema54 and ema54 > ema200:
        trend = "бычий"
        strength = 70
    elif ema8 < ema54 and ema54 < ema200:
        trend = "медвежий"
        strength = 70
    elif ema8 > ema200 and current_price > ema200:
        trend = "слабый бычий"
        strength = 40
    elif ema8 < ema200 and current_price < ema200:
        trend = "слабый медвежий"
        strength = 40
    else:
        trend = "боковик"
        strength = 20
    
    # Определяем сигналы
    signals = []
    
    # Золотой крест (EMA_8 > EMA_200)
    if ema8 > ema200:
        signals.append("Золотой крест (EMA8/EMA200)")
    
    # Смертельный крест (EMA_8 < EMA_200)
    if ema8 < ema200:
        signals.append("Смертельный крест (EMA8/EMA200)")
    
    # Цена относительно EMA
    if above_ema8 and above_ema54 and above_ema78 and above_ema200:
        signals.append("Цена выше всех EMA")
    elif not above_ema8 and not above_ema54 and not above_ema78 and not above_ema200:
        signals.append("Цена ниже всех EMA")
    
    return {
        "trend": trend,
        "strength": strength,
        "signals": signals,
        "values": {
            "EMA_8": ema8,
            "EMA_54": ema54,
            "EMA_78": ema78,
            "EMA_200": ema200
        }
    }

# -------------------- ПАТТЕРНЫ --------------------

def detect_patterns(candles: List[Dict], lookback: int = 96) -> List[str]:
    """Обнаруживает паттерны engulfing."""
    out: List[str] = []
    if len(candles) < 2:
        return out
    
    rng = candles[-min(lookback, len(candles)):]
    for i in range(1, len(rng)):
        p, c = rng[i - 1], rng[i]
        po, pc = float(p.get("open", 0)), float(p.get("close", 0))
        co, cc = float(c.get("open", 0)), float(c.get("close", 0))
        
        if pc < po and cc > co and co <= pc and cc >= po:
            out.append("🟢 Бычье поглощение")
            break
        if pc > po and cc < co and co >= pc and cc <= po:
            out.append("🔴 Медвежье поглощение")
            break
    
    return out

# -------------------- ОСНОВНАЯ ФУНКЦИЯ --------------------

# В strategy_levels.py нужно убедиться, что функция calculate_levels может принимать нормализованные свечи

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
    
    # Дополнительно можно добавить значения A и C для проверки
    levels["_base_open"] = base["open"]
    levels["_base_high"] = base["high"]
    levels["_base_low"] = base["low"]
    levels["_base_close"] = base["close"]
    
    return levels
# -------------------- EXPORT --------------------

__all__ = [
    "pick_biggest_candle",
    "calculate_levels_for_candle",
    "calculate_levels",
    "calculate_rsi",
    "rsi_series",
    "detect_patterns",
    "calculate_ema",
    "calculate_ema_series",
    "calculate_all_emas",
    "get_all_ema_series",
    "ema_trend_analysis",
]