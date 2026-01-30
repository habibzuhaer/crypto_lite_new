# -*- coding: utf-8 -*-
from __future__ import annotations

import os, time, logging, datetime, hashlib
from pathlib import Path

def ensure_dir(p: str | os.PathLike) -> None:
    Path(p).mkdir(parents=True, exist_ok=True)

def setup_logging(log_path: str, level: int = logging.INFO) -> None:
    ensure_dir(os.path.dirname(log_path))
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()]
    )

def ts_to_str_ms(ts_ms: int) -> str:
    # В будущем Python ругается на naive-UTC: оставляем явный UTC
    dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0, datetime.UTC)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# --- антиспам ключи (детерминированный) ---
_last_msg_key_ts: dict[str, float] = {}

def make_key(symbol: str, tf: str, payload: str) -> str:
    h = hashlib.sha1(payload.encode("utf-8", "ignore")).hexdigest()
    return f"{symbol}|{tf}|{h}"

def allow_send(key: str, cooldown_sec: int = 300) -> bool:
    now = time.time()
    last = _last_msg_key_ts.get(key, 0.0)
    if now - last >= cooldown_sec:
        _last_msg_key_ts[key] = now
        return True
    return False
