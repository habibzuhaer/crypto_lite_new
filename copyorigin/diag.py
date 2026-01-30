# -*- coding: utf-8 -*-
# diag.py — проверка среды, БД, построения PNG и аудит проекта

import os
import sys
import ast
import inspect
import sqlite3
import asyncio
import aiohttp
import traceback

from dotenv import load_dotenv
from typing import Dict, List

load_dotenv()

print(f"✅ ENV TELEGRAM_BOT_TOKEN — len={len(os.getenv('TELEGRAM_BOT_TOKEN',''))}")
print(f"✅ ENV TELEGRAM_CHAT_ID — {os.getenv('TELEGRAM_CHAT_ID')}")

# -------------------- ИМПОРТЫ ПРОЕКТА --------------------

import futures_bybit as fb
import strategy_levels as st
import charting as ch
import tg

# -------------------- ПРОВЕРКА БД --------------------

DB = "bot.db"
if os.path.exists(DB):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tabs = [r[0] for r in cur.fetchall()]

    if "levels" in tabs:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(levels)")]
        print(f"✅ Таблица levels найдена — колонок={len(cols)}")
        need = {"A", "C", "D", "F", "X", "Y"}
        miss = need - set(cols)
        if miss:
            print("❌ Схема levels — нет:", ",".join(miss))
        else:
            print("✅ Схема levels — содержит A,C,D,F,X,Y")
    con.close()
else:
    print("⚠️ БД bot.db не найдена")

# -------------------- PNG ПРОВЕРКА --------------------

OUT_DIR = "out_diag_png"
os.makedirs(OUT_DIR, exist_ok=True)

PAIRS = [
    ("GRTUSDT", "5m"),
    ("ADAUSDT", "15m"),
    ("INJUSDT", "15m"),
    ("LINKUSDT", "4h"),
]

NEED = ["X", "F", "f1", "A", "a1", "C", "c1", "D", "Y"]

async def scan_pair(symbol: str, tf: str):
    tag = f"[{symbol} {tf}]"
    try:
        async with aiohttp.ClientSession() as s:
            candles = await fb.fetch_kline(s, symbol, tf, 250)

            levels = st.calculate_levels(candles, symbol, tf, use_biggest_from_last=180)

            miss = [k for k in NEED if k not in levels]
            if miss:
                print(f"{tag} ❌ нет ключей {miss}")
                return

            print(f"{tag} уровни OK: A={levels['A']:.6f} C={levels['C']:.6f}")

            out = os.path.join(OUT_DIR, f"{symbol}_{tf}.png")
            try:
                ch.plot_png(candles, levels, out)
            except TypeError:
                ch.plot_png(candles, levels, out, title=f"{symbol} {tf}")

            print(f"{tag} PNG => {out}")

    except Exception as e:
        print(f"{tag} ❌ {type(e).__name__}: {e}")

# -------------------- СКАН ВСЕЙ ДИРЕКТОРИИ --------------------

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
print(f"\n📁 PROJECT ROOT = {PROJECT_ROOT}")

py_files: List[str] = []

for root, _, files in os.walk(PROJECT_ROOT):
    for f in files:
        if f.endswith(".py"):
            py_files.append(os.path.join(root, f))

print(f"📄 Найдено python-файлов: {len(py_files)}")

# -------------------- AST: ПОИСК use_biggest_from_last --------------------

bad_calls = []

for path in py_files:
    try:
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "calculate_levels":
                    for kw in node.keywords:
                        if kw.arg == "use_biggest_from_last":
                            bad_calls.append(path)

    except Exception as e:
        print(f"❌ AST error in {path}: {e}")

if bad_calls:
    print("\n⚠️ Найдены вызовы calculate_levels(... use_biggest_from_last=...)")
    for p in sorted(set(bad_calls)):
        print("   ", p)
else:
    print("\n✅ use_biggest_from_last используется корректно")

# -------------------- СИГНАТУРЫ --------------------

print("\n🔬 Проверка сигнатур")

try:
    sig = inspect.signature(st.calculate_levels)
    print("✔ calculate_levels:", sig)
except Exception:
    print("❌ calculate_levels недоступна")
    traceback.print_exc()

try:
    sig = inspect.signature(st.pick_biggest_candle)
    print("✔ pick_biggest_candle:", sig)
except Exception:
    print("❌ pick_biggest_candle недоступна")
    traceback.print_exc()

# -------------------- MAIN.PY IMPORT --------------------

print("\n🚀 Импорт main.py (без запуска)")

try:
    import main
    print("✅ main.py импортируется без ошибок")
except Exception:
    print("❌ Ошибка импорта main.py")
    traceback.print_exc()

# -------------------- RUN --------------------

async def main():
    for s, tf in PAIRS:
        await scan_pair(s, tf)

if __name__ == "__main__":
    asyncio.run(main())
