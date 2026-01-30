# diag_full_env.py
# Полная диагностика проекта crypto_lite
# НИЧЕГО НЕ МЕНЯЕТ, ТОЛЬКО ЧИТАЕТ И ПЕЧАТАЕТ

import sys
import os
import inspect
import platform
from pathlib import Path

print("\n" + "=" * 80)
print("CRYPTO_LITE — FULL DIAGNOSTIC")
print("=" * 80)

# ─────────────────────────────────────────────────────────────
# 1. PYTHON / ENV
# ─────────────────────────────────────────────────────────────
print("\n[PYTHON]")
print("executable :", sys.executable)
print("version    :", sys.version.replace("\n", " "))
print("platform   :", platform.platform())
print("cwd        :", os.getcwd())
print("venv       :", os.environ.get("VIRTUAL_ENV"))

# ─────────────────────────────────────────────────────────────
# 2. PROJECT ROOT
# ─────────────────────────────────────────────────────────────
print("\n[PROJECT ROOT]")
root = Path(__file__).resolve().parent
print("root path  :", root)
print("files:")
for p in sorted(root.iterdir()):
    if p.is_file():
        print("  -", p.name)

# ─────────────────────────────────────────────────────────────
# 3. ENV VARIABLES
# ─────────────────────────────────────────────────────────────
print("\n[ENV VARIABLES]")
env_keys = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "BYBIT_API_KEY",
    "BYBIT_API_SECRET",
    "HTML_OUTPUT_DIR",
]
for k in env_keys:
    v = os.environ.get(k)
    if v:
        masked = v[:4] + "..." + v[-4:] if len(v) > 8 else "***"
        print(f"{k:20} = {masked}")
    else:
        print(f"{k:20} = ❌ NOT SET")

# ─────────────────────────────────────────────────────────────
# 4. IMPORTS + FILE PATHS
# ─────────────────────────────────────────────────────────────
print("\n[IMPORT PATHS]")

def safe_import(name):
    try:
        mod = __import__(name)
        print(f"{name:20} OK  -> {mod.__file__}")
        return mod
    except Exception as e:
        print(f"{name:20} FAIL -> {e}")
        return None

charting = safe_import("charting")
strategy = safe_import("strategy_levels")
futures = safe_import("futures_bybit")
utils = safe_import("utils_antispam")

# ─────────────────────────────────────────────────────────────
# 5. FUNCTION CONTRACTS
# ─────────────────────────────────────────────────────────────
print("\n[FUNCTION CONTRACTS]")

def show_func(mod, name):
    if not mod or not hasattr(mod, name):
        print(f"{mod.__name__ if mod else '???'}.{name} ❌ MISSING")
        return
    fn = getattr(mod, name)
    sig = inspect.signature(fn)
    argc = fn.__code__.co_argcount
    print(f"{mod.__name__}.{name}")
    print("  signature :", sig)
    print("  argcount  :", argc)

if strategy:
    show_func(strategy, "pick_biggest_candle")
    show_func(strategy, "calculate_levels")

if charting:
    show_func(charting, "plot_png")

if utils:
    show_func(utils, "allow")
    show_func(utils, "make_key")

# ─────────────────────────────────────────────────────────────
# 6. TEST DUMMY CALL (NO NETWORK)
# ─────────────────────────────────────────────────────────────
print("\n[DUMMY FUNCTION CALL TEST]")

dummy_candle = {
    "ts": 1,
    "open": 10,
    "high": 15,
    "low": 9,
    "close": 14,
    "volume": 100,
}

dummy_candles = [dummy_candle for _ in range(10)]

if strategy and hasattr(strategy, "pick_biggest_candle"):
    try:
        b = strategy.pick_biggest_candle(dummy_candles)
        print("pick_biggest_candle() OK ->", type(b))
    except Exception as e:
        print("pick_biggest_candle() FAIL ->", e)

if charting and hasattr(charting, "plot_png"):
    try:
        charting.plot_png(
            dummy_candles,
            {"A": 10, "C": 15, "D": 20, "_base_ts": 1},
            "___diag_test.png",
            "diag test",
            "EXTRA_ARG_SHOULD_NOT_BREAK"
        )
        print("plot_png() OK with extra arg")
        if Path("___diag_test.png").exists():
            Path("___diag_test.png").unlink()
    except Exception as e:
        print("plot_png() FAIL ->", e)

# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("DIAGNOSTIC FINISHED")
print("=" * 80)
