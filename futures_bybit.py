# -*- coding: utf-8 -*-
from __future__ import annotations

import os, asyncio, logging, time
from typing import Any, Dict, List

import aiohttp
from aiohttp.client_exceptions import ClientConnectorDNSError, ClientConnectorError, ServerTimeoutError

# ── ENV ──────────────────────────────────────────────────────────────────────
BYBIT_BASE_URL = os.getenv("BYBIT_BASE_URL", "https://api.bybit.com")
# Ручное форсирование офлайна (для тестов/без сети) — 1/true/on
BYBIT_OFFLINE  = os.getenv("BYBIT_OFFLINE", "").strip().lower() in {"1","true","on","yes"}

# Тихий автоматический фолбэк в офлайн после подряд ошибок DNS/сетей
_AUTO_OFFLINE = False
_FAILS        = 0
_FAIL_LIMIT   = 3        # после 3 последовательных сетевых провалов включаем авто-оffline
_RETRY_DELAY  = 0.4      # базовая задержка между попытками
_RETRIES      = 5        # количество попыток HTTP запроса

# ── офлайн-фиктивные данные ──────────────────────────────────────────────────
# Чтобы пайплайн (уровни/картинки/сообщения) работал, когда сети нет.
def _fake_candles(symbol: str, tf: str, n: int = 250) -> List[Dict[str, Any]]:
    # простой синтетический ряд: монотония + шум
    import random
    random.seed(42 + hash(symbol) % 10_000 + hash(tf) % 10_000)
    base = {
        "ADAUSDT": 5.3,
        "WIFUSDT": 16.0,
        "INJUSDT": 65.0,
        "SOLUSDT": 75.0,
    }.get(symbol, 10.0)
    step = {"5m": 0.02, "15m": 0.03, "1h": 0.05, "4h": 0.12}.get(tf, 0.03)
    out: List[Dict[str, Any]] = []
    now_ms = int(time.time() * 1000)
    for i in range(n):
        px = base + (i - n//2) * step * 0.2
        jitter = (random.random() - 0.5) * step
        o = px + jitter
        h = o + abs(jitter) + step * 0.2
        l = o - abs(jitter) - step * 0.2
        c = o + (random.random() - 0.5) * step
        out.append({
            "ts": now_ms - (n - i) * 60_000,  # фиктивные 1-мин интервалы
            "open": round(o, 6),
            "high": round(max(h, o, c), 6),
            "low":  round(min(l, o, c), 6),
            "close": round(c, 6),
            "volume": round(1000 + random.random() * 500, 3),
        })
    return out

# ── HTTP ядро ────────────────────────────────────────────────────────────────
async def _get_json(session: aiohttp.ClientSession, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP GET с ретраями. При череде DNS/сетевых ошибок включает авто-оffline."""
    global _AUTO_OFFLINE, _FAILS
    if BYBIT_OFFLINE or _AUTO_OFFLINE:
        raise RuntimeError("OFFLINE_FAKE")

    for attempt in range(1, _RETRIES + 1):
        try:
            async with session.get(url, params=params, timeout=20) as r:
                if r.status >= 400:
                    body = (await r.text())[:500]
                    logging.warning("[BYBIT] %s -> %s: %s", url, r.status, body)
                r.raise_for_status()
                _FAILS = 0  # успех — сбрасываем счётчик
                return await r.json()
        except (ClientConnectorDNSError, ClientConnectorError, ServerTimeoutError) as e:
            _FAILS += 1
            logging.warning("[BYBIT] attempt %d failed: %s", attempt, e)
            # экспоненциальная задержка
            delay = _RETRY_DELAY * (2 ** (attempt - 1))
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _FAILS += 1
            logging.warning("[BYBIT] attempt %d failed (generic): %s", attempt, e)
            await asyncio.sleep(_RETRY_DELAY)

    # Если дошли сюда — все попытки исчерпаны
    if _FAILS >= _FAIL_LIMIT:
        _AUTO_OFFLINE = True
        logging.error("[BYBIT] auto-offline engaged after %d consecutive failures", _FAILS)
        raise RuntimeError("OFFLINE_FAKE")
    raise RuntimeError("HTTP failed after retries")

# ── Публичные функции ───────────────────────────────────────────────────────
async def fetch_kline(session: aiohttp.ClientSession, symbol: str, tf: str, limit: int = 200):
    """Возвращает массив свечей для символа/ТФ. Офлайн-режим — синтетика."""
    # Маппинг ТФ
    tf_map = {"5m": "5", "15m": "15", "1h": "60", "4h": "240"}
    interval = tf_map.get(tf, "15")
    url = f"{BYBIT_BASE_URL}/v5/market/kline"
    params = {"category": "linear", "symbol": symbol, "interval": interval, "limit": str(limit)}

    try:
        js = await _get_json(session, url, params)
        # Bybit V5 формат
        rows = (js or {}).get("result", {}).get("list", [])
        # Преобразуем в наш унифицированный вид
        out: List[Dict[str, Any]] = []
        for row in reversed(rows):  # в V5 приходят от новой к старой
            # row: [startTime, open, high, low, close, volume, turnover]
            ts = int(row[0])
            o, h, l, c = map(float, row[1:5])
            vol = float(row[5])
            out.append({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": vol})
        return out
    except RuntimeError as e:
        if str(e) == "OFFLINE_FAKE":
            return _fake_candles(symbol, tf, limit)
        raise
    except Exception:
        # На крайний случай — тоже синтетика (не роняем пайплайн)
        return _fake_candles(symbol, tf, limit)

async def get_instruments_info(session: aiohttp.ClientSession) -> dict:
    """Может быть использовано позже — сейчас возвращаем заглушку, чтобы не падать оффлайн."""
    if BYBIT_OFFLINE or _AUTO_OFFLINE:
        return {"status": "OFFLINE", "rows": []}
    url = f"{BYBIT_BASE_URL}/v5/market/instruments-info"
    params = {"category": "linear"}
    try:
        js = await _get_json(session, url, params)
        return js or {}
    except RuntimeError as e:
        if str(e) == "OFFLINE_FAKE":
            return {"status": "OFFLINE", "rows": []}
        raise
    except Exception:
        return {"status": "OFFLINE", "rows": []}

def pick_precisions(symbol: str) -> dict:
    """Простая заглушка точностей (чтобы не тянуть справочник онлайн)."""
    # Можно расширять при желании
    return {
        "price_dp": 3,
        "qty_dp": 3,
        "value_dp": 3,
    }
