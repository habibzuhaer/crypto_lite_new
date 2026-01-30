# -*- coding: utf-8 -*-
# utils_antispam.py — дедупликация сообщений по ключу и таймауту

from __future__ import annotations
import time, hashlib

_last: dict[str, float] = {}  # key -> ts

def make_key(symbol: str, tf: str, text: str) -> str:
    h = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()
    return f"{symbol}|{tf}|{h}"

def allow(key: str, cooldown_sec: int = 300) -> bool:
    now = time.time()
    ts = _last.get(key, 0.0)
    if now - ts >= cooldown_sec:
        _last[key] = now
        return True
    return False
