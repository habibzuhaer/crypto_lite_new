# -*- coding: utf-8 -*-
import asyncio, aiohttp, time
import futures_bybit as fb, strategy_legacy as st

SYMBOL = "ADAUSDT"
TF = "5m"

async def main():
    print(f"=== LEVELS TEST {SYMBOL} {TF} ===")
    async with aiohttp.ClientSession() as s:
        candles = await fb.fetch_kline(s, SYMBOL, TF, 250)
        print(f"Свечей: {len(candles)}  |  ключи: {list(candles[0].keys())}")
        base = st.pick_biggest_candle(candles)
        print("Сигнальная свеча:", base)
        levels = st.calculate_levels(candles, SYMBOL, TF)
        print("Уровни:")
        for k,v in levels.items():
            print(f"  {k}: {v}")
    print("=== END ===")

asyncio.run(main())
