# crypto_lite_new/engine/scoring.py
# SCORING LAYER
# Uses: STF market + MTF context + CME
# Does NOT calculate levels
# Does NOT trade

from typing import Dict


SCORE_THRESHOLD = 55


def run_scoring(
    *,
    stf_market: Dict,
    mtf_context: Dict,
    cme_context: Dict,
) -> Dict:
    """
    Returns:
      {
        pass: bool,
        score: int,
        direction: LONG | SHORT,
        confidence: LOW | MID | HIGH
      }
    """

    score = 0

    # ─────────────────────────────────────────────
    # 1. CME context (dominant weight)
    # ─────────────────────────────────────────────
    if cme_context.get("position") == "INSIDE":
        score += 30
    elif cme_context.get("position") == "EDGE":
        score += 15
    else:
        return _fail()

    direction = cme_context.get("bias")
    if direction not in ("LONG", "SHORT"):
        return _fail()

    # ─────────────────────────────────────────────
    # 2. STF impulse strength
    # ─────────────────────────────────────────────
    impulse_pct = stf_market.get("impulse_pct", 0.0)

    if impulse_pct >= 0.025:
        score += 25
    elif impulse_pct >= 0.018:
        score += 15
    else:
        score += 5

    # ─────────────────────────────────────────────
    # 3. Volatility confirmation
    # ─────────────────────────────────────────────
    volatility = stf_market.get("volatility", 0.0)
    if volatility > stf_market.get("impulse_pct", 0) * 1.1:
        score += 10

    # ─────────────────────────────────────────────
    # 4. MTF bias alignment (non-blocking)
    # ─────────────────────────────────────────────
    if mtf_context["bias"] == direction:
        score += min(20, mtf_context["strength"] // 3)
    elif mtf_context["bias"] == "NEUTRAL":
        score += 5
    else:
        score -= 10

    # ─────────────────────────────────────────────
    # FINAL
    # ─────────────────────────────────────────────
    if score < SCORE_THRESHOLD:
        return _fail()

    return {
        "pass": True,
        "score": int(score),
        "direction": direction,
        "confidence": _confidence(score),
    }


# ─────────────────────────────────────────────
# INTERNALS
# ─────────────────────────────────────────────

def _fail() -> Dict:
    return {
        "pass": False,
        "score": 0,
        "direction": None,
        "confidence": "LOW",
    }


def _confidence(score: int) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 65:
        return "MID"
    return "LOW"
