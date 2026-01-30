#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# levels_watcher.py — обновление уровней при выходе за диапазон X/Y

import asyncio
import statistics
from typing import List, Dict
import tg
from db import get_levels, set_levels
from strategy_legacy import calculate_levels


async def update_levels_if_needed(symbol: str, tf: str, candles: List[Dict]):
    """
    Проверяет, не пробиты ли уровни X или Y.
    Если пробиты — пересчитывает уровни по новой базовой свече и обновляет БД.
    """

    # Получаем уровни из базы
    stored = get_levels(symbol, tf)
    if not stored:
        lv = calculate_levels(candles, symbol, tf)
        set_levels(symbol, tf, lv)
        return lv

    # Проверяем текущую цену
    last_close = float(candles[-1]["close"])
    x = float(stored.get("X", 0))
    y = float(stored.get("Y", 0))

    # Если цена в диапазоне — не трогаем
    if X >= last_close >= Y:
        return stored

    # Если вышли за диапазон — пересчёт
    lv_new = calculate_levels(candles, symbol, tf)
    set_levels(symbol, tf, lv_new)

    # Сообщаем в Telegram
    msg = (
        f"⚠️ New base candle detected\n"
        f"{symbol} {tf}\n"
        f"Close={last_close:.6f}\n"
        f"Range broken ({'above X' if last_close > x else 'below Y'})"
    )
    chat_id = tg.get_chat_id()
    await tg.tg_send(chat_id, msg)

    return lv_new


# Пример теста (для одиночного запуска)
if __name__ == "__main__":
    import aiohttp
    import futures_bybit as fb

    async def main():
        pairs = [("GRTUSDT", "5m"), ("ADAUSDT", "15m"), ("INJUSDT", "15m"), ("LINKUSDT", "4h")]
        async with aiohttp.ClientSession() as s:
            for sym, tf in pairs:
                cs = await fb.fetch_kline(s, sym, tf, 250)
                lv = await update_levels_if_needed(sym, tf, cs)
                print(f"[{sym} {tf}] levels updated | base: {lv.get('A'):.6f}–{lv.get('C'):.6f}")

    asyncio.run(main())
