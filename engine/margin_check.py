# crypto_lite_new/engine/margin_check.py
# STF ONLY — hard margin requirements
# If this fails → NO CME, NO SCORING, NO LEVELS

from typing import Dict


def check_margin_requirements(stf_market: Dict) -> bool:
    """
    Margin requirements are applied ONLY on STF.
    MTF is completely ignored here.

    stf_market must contain:
      - impulse_pct
      - range_pct
      - volatility
      - candle_count
    """

    # ─────────────────────────────────────────────
    # 1. Minimal data sanity
    # ─────────────────────────────────────────────
    if stf_market is None:
        return False

    if stf_market.get("candle_count", 0) < 180:
        return False

    impulse_pct = stf_market.get("impulse_pct", 0.0)
    range_pct = stf_market.get("range_pct", 0.0)
    volatility = stf_market.get("volatility", 0.0)

    # ─────────────────────────────────────────────
    # 2. Hard impulse requirement
    # ─────────────────────────────────────────────
    # prevents weak / random candles
    if impulse_pct < 0.0167:   # 1.67%
        return False

    # ─────────────────────────────────────────────
    # 3. Range sanity check
    # ─────────────────────────────────────────────
    # avoids flat / compressed market
    if range_pct < impulse_pct * 1.2:
        return False

    # ─────────────────────────────────────────────
    # 4. Volatility floor
    # ─────────────────────────────────────────────
    # avoids dead market
    if volatility <= 0:
        return False

    # ─────────────────────────────────────────────
    # PASS
    # ─────────────────────────────────────────────
    return True
