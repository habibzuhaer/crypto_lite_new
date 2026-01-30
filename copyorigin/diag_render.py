#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, asyncio, traceback, json
from datetime import datetime, timezone
from typing import Dict, List

from dotenv import load_dotenv
load_dotenv()

# --- импорты проекта ---
import futures_bybit as fb
import strategy_levels as st
import charting as ch
import tg

CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or ""

PAIRS = [("GRTUSDT","5m"), ("ADAUSDT","15m"), ("INJUSDT","15m"), ("LINKUSDT","4h")]
OUT_DIR = "out_diag_png"

REQ_LEVEL_KEYS = ["X","D","C","c1","A","a1","F","f1","Y","_base_ts","_base_candle"]

def _ok(b: bool) -> str:
    return "✅" if b else "❌"

def _check_levels_keys(lv: Dict[str, float]) -> List[str]:
    miss = [k for k in REQ_LEVEL_KEYS if k not in lv]
    return miss

def _sig(lv: Dict[str, float]) -> str:
    return f"{int(lv.get('_base_ts',0))}|{lv.get('A',0):.10f}|{lv.get('C',0):.10f}"

def _base_str(ts_ms: int) -> str:
    return datetime.fromtimestamp(int(ts_ms)/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

async def run_one(session, symbol: str, tf: str) -> str:
    head = f"[{symbol} {tf}]"
    try:
        candles = await fb.fetch_kline(session, symbol, tf, 250)
        if not candles or not isinstance(candles, list):
            return f"{head} ❌ candles empty/bad type"

        k0 = list(candles[0].keys())
        print(f"{head} candles: len={len(candles)} keys={k0}")

        # уровни
        lv = st.calculate_levels(candles, symbol, tf)
        miss = _check_levels_keys(lv)
        if miss:
            return f"{head} ❌ levels missing keys: {miss}"

        # rsi
        if not hasattr(st, "rsi14"):
            return f"{head} ❌ strategy.rsi14 отсутствует"
        rsi = st.rsi14(candles)

        # png
        path = ch.plot_png(symbol, tf, candles, lv, OUT_DIR)

        # текст
        text = ch.build_levels_message(symbol, tf, lv, rsi, candles[-1]["close"])

        # отправка (если задан CHAT_ID)
        if CHAT_ID:
            await tg.tg_photo(CHAT_ID, path, "")
            await tg.tg_send(CHAT_ID, text)

        base_ts = lv["_base_ts"]
        sig = _sig(lv)
        return f"{head} {_ok(True)} PNG={os.path.basename(path)} base={_base_str(base_ts)} sig={sig}"
    except Exception as e:
        tb = traceback.format_exc(limit=1)
        return f"{head} ❌ {e.__class__.__name__}: {e}\n{tb}"

async def main():
    print("=== DIAG RENDER ===")
    print(f"CHAT_ID set: {_ok(bool(CHAT_ID))}")
    import aiohttp
    res = []
    async with aiohttp.ClientSession() as s:
        for sym, tf in PAIRS:
            res.append(await run_one(s, sym, tf))
    print("\n--- SUMMARY ---")
    for line in res:
        print(line)

if __name__ == "__main__":
    asyncio.run(main())
