#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import math
import asyncio
from datetime import datetime, timezone

import aiohttp
from dotenv import load_dotenv

import tg
import futures_bybit as fb
import strategy_legacy as st
import charting as ch

# ----- ПАРЫ ДЛЯ ПУБЛИКАЦИИ (как в проекте) -----
PAIRS = [("GRTUSDT", "5m"), ("ADAUSDT", "15m"), ("INJUSDT", "15m"), ("LINKUSDT", "4h")]

# ----- ОБЩИЕ НАСТРОЙКИ -----
OUT_DIR = "out_diag_png"  # куда сохраняем PNG
os.makedirs(OUT_DIR, exist_ok=True)

def fmt(x: float) -> str:
    # Нормализованный формат цены (без научной нотации, обрезка нулей справа)
    s = f"{x:.6f}"
    return s.rstrip("0").rstrip(".") if "." in s else s

def rsi_emoji(val: float) -> str:
    # зелёный / жёлтый / красный индикатор
    if val >= 60:
        return "🟢"
    if val <= 40:
        return "🔴"
    return "🟡"

def caption_from_levels(sym: str, tf: str, lv: dict, rsi_val: float, pct_move: float) -> str:
    base_dt = datetime.fromtimestamp(lv["_base_ts"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S (UTC)")
    lines = []
    lines.append(f"#{sym} ТФ: {tf}")
    lines.append(f"Δ% свечи: {pct_move:.2f}%")
    lines.append(f"base: {base_dt}")
    lines.append(f"RSI14: {rsi_val:.1f} {rsi_emoji(rsi_val)}")
    lines.append("Уровни:")
    # Порядок вывода, как обсуждали
    for key in ["X", "D", "C", "A", "F", "Y", "f1", "a1", "c1"]:
        if key in lv:
            lines.append(f"{key}: {fmt(lv[key])}")
    return "\n".join(lines)

async def render_and_send(session: aiohttp.ClientSession, chat_id: str, sym: str, tf: str) -> None:
    # 1) Котировки
    candles = await fb.fetch_kline(session, sym, tf, 250)

    # 2) Уровни
    lv = st.calculate_levels(candles, sym, tf)

    # 3) RSI последнего окна
    try:
        rsi_series = st.rsi14_series(candles)
        rsi_val = float(rsi_series[-1]) if hasattr(rsi_series, "__len__") else float(rsi_series)
    except Exception:
        rsi_val = 50.0

    # 4) Δ% по базовой свече
    base = lv["_base_candle"]
    pct_move = abs((base["close"] - base["open"]) / base["open"]) * 100.0 if base["open"] else 0.0

    # 5) Рендер PNG
    path_png = ch.plot_png(sym, tf, candles, lv, OUT_DIR)

    # 6) Подпись и отправка ОДНИМ сообщением (фото + caption)
    caption = caption_from_levels(sym, tf, lv, rsi_val, pct_move)
    await tg.tg_photo(chat_id, path_png, caption)

async def main():
    load_dotenv()
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is not set")

    async with aiohttp.ClientSession() as s:
        # Принудительно обрабатываем все пары по очереди
        for sym, tf in PAIRS:
            try:
                await render_and_send(s, chat_id, sym, tf)
                print(f"[FORCE] sent {sym} {tf}")
            except Exception as e:
                print(f"[FORCE][ERROR] {sym} {tf}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
