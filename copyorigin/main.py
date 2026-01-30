# -*- coding: utf-8 -*-
from __future__ import annotations

import os, asyncio, logging, time
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
import aiohttp

from futures_bybit import fetch_kline
from strategy_levels import calculate_levels, pick_biggest_candle
from charting import plot_png
from tg import TGQ, kb_main
from engine_paper import place_limit, place_tp, place_sl, cancel, positions, get_balance
from trend_detector import analyze_trend
from strategy_legacy import detect_patterns


load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

OUT_DIR = str(Path("out").resolve())
Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

SYMBOLS_TFS = {
    "GRTUSDT": ["5m", "1h"],
    "LINKUSDT": ["15m", "4h"],
    "ADAUSDT": ["15m", "1h"],
    "INJUSDT": ["15m", "1h"],
}

TF_MIN = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}

_last_state: Dict[str, str] = {}
_last_sent_candle_ts: Dict[str, int] = {}
_last_price: Dict[str, float] = {}
_last_banner_ts: float = 0.0

_break_mode: Dict[str, str] = {}
_break_count: Dict[str, int] = {}
_break_latched: Dict[str, bool] = {}
_latched_on_ts: Dict[str, int] = {}
_wait_new_candle: Dict[str, bool] = {}

def _key(symbol: str, tf: str) -> str:
    return f"{symbol}|{tf}"

def _state_signature(levels):
    return "|".join(
        f"{levels[k]:.8f}"
        for k in ("X", "A", "C", "D", "F", "Y")
        if k in levels
    ) + f"|base={levels.get('_base_ts', 0)}"

def _bars_24h(tf: str) -> int:
    return max(1, (24 * 60) // TF_MIN.get(tf, 5))

def _ts_to_local_str(ts_ms: int) -> str:
    t = time.localtime(ts_ms // 1000)
    return time.strftime("%Y-%m-%d %H:%M", t)

def _rsi_tag(rsi: Optional[float]) -> str:
    if rsi is None:
        return "—"
    if rsi >= 70:
        return f"{rsi:.1f} 🔴 (перекупленность)"
    if rsi <= 30:
        return f"{rsi:.1f} 🟢 (перепроданность)"
    return f"{rsi:.1f} 🟡 (нейтрально)"

def _format_caption(symbol: str, tf: str, candles: List[dict],
                    levels: Dict[str, float], rsi14: Optional[float],
                    pats: List[str], trend_info: Optional[Dict]) -> str:
    c = candles[-1]
    price = float(c.get("close", 0.0))
    ts_local = _ts_to_local_str(int(c.get("ts", 0)))
    num = len(candles)

    lvl_lines = [f"{k}: {levels[k]:.6f}" for k in ("X", "A", "C", "D", "F", "Y") if k in levels]
    levels_text = "\n".join(lvl_lines)

    lines = [
        f"🟢 <b>#{symbol}</b> ТФ: <b>{tf}</b>",
        f"Цена: <b>{price:.4f}</b>",
        f"Свеча №{num}, дата (лок.): <b>{ts_local}</b>",
        "\n📊 <b>Уровни:</b>",
        levels_text,
        "\nДоп. факторы за последние 24 часа",
        ", ".join(pats) if pats else "Нет дополнительных факторов",
        f"\nRSI14: {_rsi_tag(rsi14)}",
    ]

    if trend_info and trend_info["trend"] != "neutral":
        lines.append(
            f"\n📈 Тренд: <b>{trend_info['trend'].upper()}</b> "
            f"({trend_info['confidence']*100:.0f}%)"
        )

    return "\n".join(lines)

async def _fetch_with_retry(sess: aiohttp.ClientSession, symbol: str, tf: str, limit: int = 250):
    for attempt, delay in enumerate([0, 1, 2, 4, 8], start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            return await fetch_kline(sess, symbol, tf, limit=limit)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            logging.warning("[BYBIT] attempt %s failed: %s", attempt, e)
    return None

def _update_break_state(key: str, close_price: float, levels: Dict[str, float], curr_ts: int) -> None:
    x = levels.get("X")
    y = levels.get("Y")
    if x is None or y is None:
        _break_mode[key] = "inside"
        _break_count[key] = 0
        _break_latched[key] = False
        _wait_new_candle[key] = False
        _latched_on_ts[key] = -1
        return

    if close_price > float(y):
        mode = "aboveY"
    elif close_price < float(x):
        mode = "belowX"
    else:
        mode = "inside"

    prev_mode = _break_mode.get(key, "inside")
    if mode == "inside":
        _break_mode[key] = "inside"
        _break_count[key] = 0
        _break_latched[key] = False
        _wait_new_candle[key] = False
        _latched_on_ts[key] = -1
        return

    if mode == prev_mode:
        _break_count[key] = _break_count.get(key, 0) + 1
    else:
        _break_mode[key] = mode
        _break_count[key] = 1

    if _break_count[key] >= 6:
        if not _break_latched.get(key, False):
            _latched_on_ts[key] = curr_ts
        _break_latched[key] = True
        _wait_new_candle[key] = True

async def run_symbol_tf(sess: aiohttp.ClientSession, tg: TGQ, symbol: str, tf: str) -> bool:
    key = _key(symbol, tf)
    try:
        candles = await _fetch_with_retry(sess, symbol, tf)
        if not candles:
            logging.warning("[WARN] no candles %s/%s", symbol, tf)
            return False

        c_last = candles[-1]
        curr_price = float(c_last["close"])
        curr_ts = int(c_last["ts"])

        if _last_sent_candle_ts.get(key) == curr_ts:
            return False

        levels = calculate_levels(candles, symbol, tf, use_biggest_from_last=240)

        base = pick_biggest_candle(candles[-240:])
        if base and "ts" in base:
            levels["_base_ts"] = base["ts"]

        lookback = min(len(candles), _bars_24h(tf))
        pats = detect_patterns(candles[-lookback:])
        state = _state_signature(levels)

        if tf == "5m":
            tf_higher = "30m"
        elif tf == "15m":
            tf_higher = "1h"
        elif tf == "1h":
            tf_higher = "4h"
        else:
            tf_higher = tf

        candles_higher = await _fetch_with_retry(sess, symbol, tf_higher, limit=120)
        trend_info = analyze_trend(candles, candles_higher)

        rsi14 = trend_info["rsi"] if trend_info else None

        if trend_info:
            logging.info(
                f"[TREND] {symbol}/{tf} → {trend_info['trend'].upper()} "
                f"({trend_info['confidence']*100:.0f}%) RSI={trend_info['rsi']:.1f}"
            )

        _update_break_state(key, curr_price, levels, curr_ts)
        latched = _break_latched.get(key, False)
        latched_ts = _latched_on_ts.get(key, -1)
        need_new = _wait_new_candle.get(key, False)

        if not (latched and need_new and curr_ts != latched_ts and curr_ts > latched_ts >= 0):
            _last_price[key] = curr_price
            return False

        if _last_state.get(key) == state:
            _last_price[key] = curr_price
            return False

        img_path = os.path.join(OUT_DIR, f"{symbol}_{tf}.png")
        try:
            plot_png(candles, levels, img_path, title=f"{symbol} {tf} RSI={rsi14:.1f}")
        except TypeError:
            plot_png(candles, levels, img_path)

        cap = _format_caption(symbol, tf, candles, levels, rsi14, pats, trend_info)
        ok = await tg.send_photo(img_path, cap)
        if ok:
            _last_state[key] = state
            _last_sent_candle_ts[key] = curr_ts
            _last_price[key] = curr_price
            _wait_new_candle[key] = False
            logging.info("[INFO] sent %s/%s", symbol, tf)
            return True

        _last_price[key] = curr_price
        return False

    except Exception as e:
        logging.warning("[ERROR] %s/%s: %s", symbol, tf, e)
        return False

async def main_loop() -> None:
    global _last_banner_ts
    tg = TGQ()
    TF_SLEEP = 60
    sess = aiohttp.ClientSession()
    try:
        while True:
            sent_count = 0
            try:
                for s, tfs in SYMBOLS_TFS.items():
                    for tf in tfs:
                        if await run_symbol_tf(sess, tg, s, tf):
                            sent_count += 1
                        await asyncio.sleep(0.05)

                now = time.time()
                if sent_count > 0 and (now - _last_banner_ts) >= 1800:
                    if await tg.send_text("📊 <b>Market Monitor</b>", kb_main()):
                        _last_banner_ts = now

            except Exception as e:
                logging.warning("loop err: %s", e)

            await asyncio.sleep(TF_SLEEP)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        try:
            await sess.close()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
