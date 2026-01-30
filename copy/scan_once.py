# -*- coding: utf-8 -*-
# scan_once.py — точечная диагностика сканера/уровней/рендера без правок проекта
import os, asyncio, json, traceback
from dotenv import load_dotenv
load_dotenv()

import aiohttp
import futures_bybit as fb
import strategy_levels as st
import charting as ch
import tg
tgq = tg.TGQ()

PAIRS = [("GRTUSDT","5m"), ("ADAUSDT","15m"), ("INJUSDT","15m"), ("LINKUSDT","4h")]
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OUT_DIR = "out_diag_png"; os.makedirs(OUT_DIR, exist_ok=True)

NEED_KEYS = ("X","F","f1","A","a1","C","c1","D","Y")

def pfx(sym, tf): return f"[{sym} {tf}]"

def describe_candles(candles):
    info = {"type": type(candles).__name__, "len": len(candles) if hasattr(candles, "__len__") else None}
    try:
        c0 = candles[0]
        info["item0_type"] = type(c0).__name__
        if isinstance(c0, dict):
            info["item0_keys"] = list(c0.keys())
        else:
            info["item0_preview"] = str(c0)[:120]
    except Exception as e:
        info["item0_err"] = f"{type(e).__name__}: {e}"
    return info

async def scan_one(session, symbol, tf):
    tag = pfx(symbol, tf)
    try:
        candles = await fb.fetch_kline(session, symbol, tf, 250)
    except Exception as e:
        return f"{tag} ❌ fetch_kline: {type(e).__name__}: {e}"

    if not candles or len(candles) < 180:
        return f"{tag} ❌ candles empty/short, info={describe_candles(candles)}"

    # печать структуры свечей
    info = describe_candles(candles)
    print(f"{tag} candles: {json.dumps(info, ensure_ascii=False)}")

    # шаг 1: pick_biggest_candle
    try:
        base = st.pick_biggest_candle(candles)
        ok_base = isinstance(base, dict) and {"ts","open","high","low","close"} <= set(base.keys())
        print(f"{tag} base_ok={ok_base} base_type={type(base).__name__}")
        if not ok_base:
            return f"{tag} ❌ base invalid: {base}"
    except Exception as e:
        tb = traceback.format_exc(limit=2)
        return f"{tag} ❌ pick_biggest_candle: {type(e).__name__}: {e}\n{tb}"

    # шаг 2: calculate_levels(candles, symbol, tf)
    try:
        lv = st.calculate_levels(candles, symbol, tf)
    except Exception as e:
        tb = traceback.format_exc(limit=2)
        return f"{tag} ❌ calculate_levels: {type(e).__name__}: {e}\n{tb}"

    miss = [k for k in NEED_KEYS if k not in lv]
    if miss:
        return f"{tag} ❌ levels missing={miss}, keys={sorted(lv.keys())}"
    print(f"{tag} levels OK: A={lv['A']}, C={lv['C']}, D={lv['D']}")

    # шаг 3: plot_png(candles, levels, symbol, tf, out_path)
    png_path = os.path.join(OUT_DIR, f"{symbol}_{tf}.png")
    try:
        ch.plot_png(
            candles,
            lv,
            png_path,
            f"{symbol} {tf}"
        )

    except TypeError as e:
        # покажем фактическую сигнатуру функции в charting
        sig = None
        try:
            import inspect
            sig = str(inspect.signature(ch.plot_png))
        except Exception:
            pass
        return f"{tag} ❌ plot_png TypeError: {e} | signature={sig}"
    except Exception as e:
        tb = traceback.format_exc(limit=2)
        return f"{tag} ❌ plot_png: {type(e).__name__}: {e}\n{tb}"

    ok_png = os.path.exists(png_path) and os.path.getsize(png_path) > 2000
    print(f"{tag} PNG => {png_path} size={os.path.getsize(png_path) if os.path.exists(png_path) else 0}")
    
    if CHAT_ID and ok_png:
        try:
            await tgq.send_text(f"✅ {symbol} {tf} PNG тест")
            await tgq.send_photo(png_path)
        except Exception as e:
            print(f"{tag} ⚠️ tg send fail: {type(e).__name__}: {e}")

    return f"{tag} OK"

async def main():
    results = []
    async with aiohttp.ClientSession() as s:
        for sym, tf in PAIRS:
            res = await scan_one(s, sym, tf)
            print(res); results.append(res)
    print("\n--- SUMMARY ---")
    for r in results: print(r)

if __name__ == "__main__":
    asyncio.run(main())