# -*- coding: utf-8 -*-
# ticker_format.py — хранение и автообновление точности цен и объёмов

import os, json, aiohttp, asyncio, time

CACHE_FILE = os.path.join(os.path.dirname(__file__), "ticker_precisions.json")
BYBIT_URL = "https://api.bybit.com/v5/market/instruments-info?category=linear"

# ─────────────────────────────────────────────
async def fetch_precisions():
    """Тянет все USDT тикеры с точностью"""
    async with aiohttp.ClientSession() as s:
        async with s.get(BYBIT_URL) as r:
            data = await r.json()
            precisions = {}
            for i in data.get("result", {}).get("list", []):
                symbol = i.get("symbol")
                if not symbol or not symbol.endswith("USDT"):
                    continue
                price_dec = int(i.get("pricePrecision", 2))
                qty_step = i.get("lotSizeFilter", {}).get("qtyStep", "0.01")
                qty_dec = qty_step[::-1].find(".")
                precisions[symbol] = {
                    "price_decimal": price_dec,
                    "qty_decimal": max(qty_dec, 0),
                }
            with open(CACHE_FILE, "w") as f:
                json.dump(precisions, f, indent=2)
            return precisions

def load_precisions():
    """Загрузка из кэша"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}

def cache_expired(hours=24):
    """Проверка срока годности кэша"""
    if not os.path.exists(CACHE_FILE):
        return True
    mtime = os.path.getmtime(CACHE_FILE)
    return (time.time() - mtime) > hours * 3600

# ─────────────────────────────────────────────
def format_price(symbol, price):
    """Форматирует цену, как на бирже (с автоподтяжкой точности)"""
    precisions = load_precisions()
    if symbol not in precisions or cache_expired():
        asyncio.run(fetch_precisions())
        precisions = load_precisions()
    d = precisions.get(symbol, {"price_decimal": 2})
    return f"{float(price):.{d['price_decimal']}f}"

def format_qty(symbol, qty):
    """Форматирует количество, как на бирже"""
    precisions = load_precisions()
    if symbol not in precisions or cache_expired():
        asyncio.run(fetch_precisions())
        precisions = load_precisions()
    d = precisions.get(symbol, {"qty_decimal": 2})
    return f"{float(qty):.{d['qty_decimal']}f}"

# ─────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(fetch_precisions())
    print(f"✅ Справочник точностей обновлён и сохранён в {CACHE_FILE}")
