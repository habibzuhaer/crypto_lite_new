# crypto_lite_new/engine/levels_acdfxy.py
# ACDFXY LEVELS
# Called ONLY after:
# - margin pass
# - CME pass
# - scoring pass

from typing import Dict, Optional

from strategies.final_candle import pick_final_candle
from utils.decimals import round_price


def calculate_acdfxy_levels(
    *,
    stf_market: Dict,
    direction: str,
) -> Optional[Dict]:
    """
    Returns:
      {
        candle_id,
        levels: {
          A, C, D, F, X, Y,
          TP1, TP2, TP3,
          SL
        }
      }
    """

    candles = stf_market.get("candles")
    if not candles or len(candles) < 180:
        return None

    # ─────────────────────────────────────────────
    # 1. Pick FINAL candle (your strict logic)
    # ─────────────────────────────────────────────
    final_candle = pick_final_candle(candles, direction)
    if final_candle is None:
        return None

    o = float(final_candle["open"])
    h = float(final_candle["high"])
    l = float(final_candle["low"])
    c = float(final_candle["close"])
    price_decimals = final_candle.get("price_decimal", 2)

    # Candle body logic (STRICT)
    if direction == "LONG":
        base_low = o
        base_high = h
    else:
        base_low = l
        base_high = o

    impulse = abs(base_high - base_low)
    if impulse <= 0:
        return None

    # ─────────────────────────────────────────────
    # 2. Core levels
    # ─────────────────────────────────────────────
    A = base_high
    C = base_low

    delta = abs(A - C)

    D = A + delta if direction == "LONG" else C - delta
    F = C - delta if direction == "LONG" else A + delta

    # Extended levels
    X = D + delta * 0.5 if direction == "LONG" else D - delta * 0.5
    Y = F - delta * 0.5 if direction == "LONG" else F + delta * 0.5

    # ─────────────────────────────────────────────
    # 3. Targets and Stop
    # ─────────────────────────────────────────────
    TP1 = A + delta * 0.5 if direction == "LONG" else A - delta * 0.5
    TP2 = D
    TP3 = X

    SL = C - delta * 0.25 if direction == "LONG" else C + delta * 0.25

    # ─────────────────────────────────────────────
    # 4. Rounding
    # ─────────────────────────────────────────────
    levels = {
        "A": round_price(A, price_decimals),
        "C": round_price(C, price_decimals),
        "D": round_price(D, price_decimals),
        "F": round_price(F, price_decimals),
        "X": round_price(X, price_decimals),
        "Y": round_price(Y, price_decimals),
        "TP1": round_price(TP1, price_decimals),
        "TP2": round_price(TP2, price_decimals),
        "TP3": round_price(TP3, price_decimals),
        "SL": round_price(SL, price_decimals),
    }

    return {
        "candle_id": final_candle.get("id"),
        "levels": levels,
    }
