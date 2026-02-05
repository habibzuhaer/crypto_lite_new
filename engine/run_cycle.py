# crypto_lite_new/engine/run_cycle.py
# SINGLE ENTRY POINT
# Order is STRICT. Do not change.

from typing import Optional
from datetime import datetime

from engine.stf_market import load_stf_market
from engine.margin_check import check_margin_requirements
from engine.cme_gate import check_cme_gate
from engine.mtf_context import build_mtf_context
from engine.scoring import run_scoring
from engine.levels_acdfxy import calculate_acdfxy_levels
from engine.contract import SignalContract


def run_cycle(symbol: str, timeframe: str) -> Optional[SignalContract]:
    """
    Main execution cycle.

    STF:
      - margin requirements
      - CME gate
      - scoring
      - ACDFXY

    MTF:
      - context only (no margin, no levels)

    Returns:
      SignalContract or None
    """

    # ─────────────────────────────────────────────
    # 1. Load STF market data (180 candles, impulse, volatility)
    # ─────────────────────────────────────────────
    stf_market = load_stf_market(symbol, timeframe)
    if stf_market is None:
        return None

    # ─────────────────────────────────────────────
    # 2. Margin requirements (STF ONLY)
    # ─────────────────────────────────────────────
    margin_pass = check_margin_requirements(stf_market)
    if not margin_pass:
        return None

    # ─────────────────────────────────────────────
    # 3. CME hard gate
    # ─────────────────────────────────────────────
    cme_context = check_cme_gate(symbol)
    if not cme_context["pass"]:
        return None

    # ─────────────────────────────────────────────
    # 4. MTF context (NO margin, NO levels)
    # ─────────────────────────────────────────────
    mtf_context = build_mtf_context(symbol)

    # ─────────────────────────────────────────────
    # 5. Scoring (CME + STF + MTF)
    # ─────────────────────────────────────────────
    score_result = run_scoring(
        stf_market=stf_market,
        mtf_context=mtf_context,
        cme_context=cme_context,
    )

    if not score_result["pass"]:
        return None

    # ─────────────────────────────────────────────
    # 6. ACDFXY levels (ONLY AFTER ALL PASS)
    # ─────────────────────────────────────────────
    levels_result = calculate_acdfxy_levels(
        stf_market=stf_market,
        direction=score_result["direction"],
    )

    if levels_result is None:
        return None

    # ─────────────────────────────────────────────
    # 7. Signal contract (ONLY OUTPUT)
    # ─────────────────────────────────────────────
    return SignalContract(
        symbol=symbol,
        timeframe=timeframe,
        direction=score_result["direction"],
        score=score_result["score"],
        mtf_bias=mtf_context["bias"],
        cme_context=cme_context,
        margin_pass=True,
        levels=levels_result["levels"],
        candle_id=levels_result["candle_id"],
        timestamp=datetime.utcnow().isoformat(),
    )
