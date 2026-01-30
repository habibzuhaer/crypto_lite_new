# -*- coding: utf-8 -*-
# diag_full.py — расширенная диагностика окружения и конфигурации проекта

import os, sys, sqlite3, inspect
from dotenv import load_dotenv
import importlib
load_dotenv()

def env(name, mask=False):
    v = os.getenv(name)
    if not v:
        print(f"❌ ENV {name} — отсутствует")
        return
    if mask:
        print(f"✅ ENV {name} — len={len(v)}, mask={v[:6]}…{v[-6:]}")
    else:
        print(f"✅ ENV {name} = {v}")

print("=== ENVIRONMENT ===")
for var in ["TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID","BYBIT_API_KEY","BYBIT_API_SECRET","HTML_OUTPUT_DIR"]:
    env(var, mask=True)

print("\n=== CONFIG & STRUCTURE ===")
try:
    cfg = importlib.import_module("config")
    print("✅ config.py найден")
    if hasattr(cfg, "TRADING_GROUPS"):
        g = cfg.TRADING_GROUPS
        print(f"✅ TRADING_GROUPS: {len(g)} групп, пример -> {list(g.keys())[:2]}")
    if hasattr(cfg, "SYMBOL_TO_NAME"):
        s = cfg.SYMBOL_TO_NAME
        print(f"✅ SYMBOL_TO_NAME: {len(s)} тикеров, пример -> {list(s)[:3]}")
except Exception as e:
    print("❌ Ошибка импорта config.py:", e)

print("\n=== SQLITE ===")
try:
    db="bot.db"
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tabs = [r[0] for r in cur.fetchall()]
    print(f"✅ Таблицы: {', '.join(tabs)}")
    for t in tabs:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [r[1] for r in cur.fetchall()]
        print(f"   - {t}: {len(cols)} колонок ({', '.join(cols[:8])}...)")
    con.close()
except Exception as e:
    print("❌ Ошибка SQLite:", e)

print("\n=== MODULES & FUNCTIONS ===")
for mod in ["strategy","charting","futures_bybit","engine_paper","db","tg"]:
    try:
        m = importlib.import_module(mod)
        funcs = [n for n, o in inspect.getmembers(m, inspect.isfunction)]
        print(f"✅ {mod}: {len(funcs)} функций ({', '.join(funcs[:6])}...)")
    except Exception as e:
        print(f"❌ {mod}: {e}")

print("\n=== PATHS ===")
for d in ["out","out_diag_png","logs","www"]:
    full = os.path.join(os.getcwd(), d)
    print(("✅" if os.path.isdir(full) else "❌") + f" {d} -> {full}")

print("\n=== SUMMARY ===")
print("✅ Проверены ENV, config, база, функции и каталоги.")
print("Если нет ❌ — проект полностью цел и готов к запуску.")
