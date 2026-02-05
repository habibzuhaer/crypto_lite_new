# crypto_lite_new/engine/mtf_context.py
# MTF CONTEXT ONLY
# No margin, no CME, no levels, no blocking

from typing import Dict, List

from data.futures_bybit import fetch_klines
from utils.timeframes import MTF_TIMEFRAMES


def build_mtf_context(symbol: str) -> Dict:
    """
    Builds multi-timeframe context.
    This context NEVER blocks signals directly.
    Used ONLY by scoring.

    Returns:
      {
        bias: LONG | SHORT | NEUTRAL,
        strength: 0..100,
        trend_state: impulsive | corrective | flat
      }
    """

    biases: List[str] = []
    strengths: List[float] = []

    for tf in MTF_TIMEFRAMES:
        candles = fetch_klines(symbol=symbol, timeframe=tf, limit=120)
        if not candles or len(candles) < 50:
            continue

        bias, strength = _analyze_tf_bias(candles)
        biases.append(bias)
        strengths.append(strength)

    if not biases:
        return {
            "bias": "NEUTRAL",
            "strength": 0,
            "trend_state": "flat",
        }

    final_bias = _merge_biases(biases)
    avg_strength = int(sum(strengths) / len(strengths))

    return {
        "bias": final_bias,
        "strength": avg_strength,
        "trend_state": _trend_state_from_strength(avg_strength),
    }


# ─────────────────────────────────────────────
# INTERNALS
# ─────────────────────────────────────────────

def _analyze_tf_bias(candles: List[Dict]) -> (str, float):
    """
    Very simple directional context.
    No precision needed — only bias.
    """

    up = 0
    down = 0

    for c in candles[-30:]:
        if c["close"] > c["open"]:
            up += 1
        else:
            down += 1

    total = up + down
    if total == 0:
        return "NEUTRAL", 0

    strength = abs(up - down) / total * 100

    if up > down:
        return "LONG", strength
    if down > up:
        return "SHORT", strength

    return "NEUTRAL", 0


def _merge_biases(biases: List[str]) -> str:
    if biases.count("LONG") > biases.count("SHORT"):
        return "LONG"
    if biases.count("SHORT") > biases.count("LONG"):
        return "SHORT"
    return "NEUTRAL"


def _trend_state_from_strength(strength: int) -> str:
    if strength >= 65:
        return "impulsive"
    if strength >= 35:
        return "corrective"
    return "flat"
