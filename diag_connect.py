# -*- coding: utf-8 -*-
import os, aiohttp, asyncio, sqlite3, time
from dotenv import load_dotenv
import tg, futures_bybit, charting

load_dotenv()
TOK = os.getenv("TELEGRAM_BOT_TOKEN")
CID = os.getenv("TELEGRAM_CHAT_ID")
KEY = os.getenv("BYBIT_API_KEY")
SEC = os.getenv("BYBIT_API_SECRET")

def db_check():
    if not os.path.exists("bot.db"):
        return "❌ bot.db отсутствует"
    con = sqlite3.connect("bot.db"); cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    con.close()
    return f"✅ SQLite OK, таблицы: {tables}"

async def test_tg():
    try:
        await tg.tg_send(CID, "✅ test_tg: соединение с Telegram активно")
        return "✅ Telegram отправка работает"
    except Exception as e:
        return f"❌ Telegram ошибка: {e}"

async def test_bybit():
    try:
        async with aiohttp.ClientSession() as s:
            candles = await futures_bybit.fetch_kline(s, "ADAUSDT", "5m", 10)
            if isinstance(candles, list) and candles and "close" in candles[-1]:
                return f"✅ Bybit OK, {len(candles)} свечей"
            return f"❌ Bybit fetch_kline вернул {type(candles)}"
    except Exception as e:
        return f"❌ Bybit ошибка: {e}"

async def test_png():
    try:
        os.makedirs("out_diag_png", exist_ok=True)
        levels = {"A": 1.0, "C": 2.0, "D": 3.0, "F": 4.0, "X": 0.5, "Y": 4.5}
        candles = [
            {"ts": int(time.time()*1000)+i*60000, "open":1, "high":2, "low":0.8, "close":1.5, "volume":100}
            for i in range(10)
        ]
        path = charting.plot_png("TESTUSDT", "5m", candles, levels, "out_diag_png")
        return f"✅ charting OK: {path}"
    except Exception as e:
        return f"❌ charting ошибка: {e}"

async def main():
    print("=== CONNECTIVITY TEST ===")
    print(db_check())
    print(await test_tg())
    print(await test_bybit())
    print(await test_png())
    print("=== END ===")

asyncio.run(main())
