# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
load_dotenv()

# -------- TELEGRAM --------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
WHITELIST_USERNAMES = ["admin", "root", "Rich8_alertBot"]

# -------- BYBIT / DATA --------
BYBIT_API_KEY    = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")
HTML_OUTPUT_DIR  = os.getenv("HTML_OUTPUT_DIR", "/data/data/com.termux/files/home/www")
ML_OUTPUT_DIR    = os.path.join(HTML_OUTPUT_DIR, "ml")
EXPORT_PASSWORD  = "rich_export_2025"

# -------- ПАРЫ И ТАЙМФРЕЙМЫ --------
SYMBOLS = ["GRTUSDT","ADAUSDT","INJUSDT","LINKUSDT"]
TF_LIST = ["5","15","60","240"]
MAX_CANDLES = 250

# -------- СКАН ИНТЕРВАЛЫ --------
POLL_SEC_FAST = 60     # для 5m и 15m
POLL_SEC_SLOW = 180    # для 1h и 4h
