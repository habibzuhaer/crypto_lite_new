#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import math
import asyncio
from datetime import datetime, timezone
import time

import aiohttp
from dotenv import load_dotenv

import tg
import futures_bybit as fb
import strategy_levels as st
import charting as ch

# ОБНОВЛЁННЫЙ СПИСОК ПАР ДЛЯ ПРИНУДИТЕЛЬНОЙ ОТПРАВКИ
PAIRS = [
    ("GRTUSDT", "5m"),
    ("GRTUSDT", "1h"),
    ("LINKUSDT", "15m"),
    ("LINKUSDT", "4h"),
    ("ADAUSDT", "15m"),
    ("ADAUSDT", "1h"),
    ("INJUSDT", "15m"),
    ("INJUSDT", "1h"),
]

# ----- ОБЩИЕ НАСТРОЙКИ -----
OUT_DIR = "out_diag_png"  # куда сохраняем PNG
os.makedirs(OUT_DIR, exist_ok=True)

def fmt(x: float) -> str:
    # Нормализованный формат цены (без научной нотации, обрезка нулей справа)
    s = f"{x:.6f}"
    return s.rstrip("0").rstrip(".") if "." in s else s

def rsi_emoji(val: float) -> str:
    # зелёный / жёлтый / красный индикатор
    if val >= 60:
        return "🟢"
    if val <= 40:
        return "🔴"
    return "🟡"

def _ts_to_human_str(ts_ms: int) -> str:
    """Преобразует timestamp в читаемое время с указанием дня недели."""
    if ts_ms <= 0:
        return "N/A"
    
    t = time.localtime(ts_ms // 1000)
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    day_of_week = days[t.tm_wday]
    
    return time.strftime(f"%d.%m.%Y {day_of_week} %H:%M", t)

def _get_candle_time_range(candle: Dict, tf: str) -> Tuple[str, str]:
    """Возвращает время открытия и закрытия свечи."""
    ts_ms = int(candle.get("ts", 0))
    if ts_ms <= 0:
        return "N/A", "N/A"
    
    # Определяем длительность свечи в миллисекундах
    tf_duration_ms = {
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000
    }
    
    open_time = _ts_to_human_str(ts_ms)
    close_ts = ts_ms + tf_duration_ms.get(tf, 60 * 60 * 1000)
    close_time = _ts_to_human_str(close_ts)
    
    return open_time, close_time

def caption_from_levels(sym: str, tf: str, lv: dict, rsi_val: float, pct_move: float, emas: dict, current_price: float, last_candle: dict) -> str:
    # Получаем время открытия и закрытия свечи
    open_time, close_time = _get_candle_time_range(last_candle, tf)
    
    lines = []
    lines.append(f"<b>#{sym} ТФ: {tf}</b>")
    lines.append(f"Цена: {current_price:.6f}")
    lines.append(f"Время свечи: открытие {open_time} - закрытие {close_time}")
    lines.append(f"Анализ: последние 250 свечей")
    
    # Базовая свеча
    base_ts = lv.get("_base_ts", 0)
    if base_ts > 0:
        base_time = _ts_to_human_str(base_ts)
        lines.append(f"Базовая свеча: {base_time}")
    
    lines.append(f"Δ% свечи: {pct_move:.2f}%")
    lines.append(f"RSI14: {rsi_val:.1f} {rsi_emoji(rsi_val)}")
    
    lines.append("\n<b>Основные уровни:</b>")
    for key in ["X", "F", "A", "C", "D", "Y"]:
        if key in lv:
            lines.append(f"{key}: {fmt(lv[key])}")
    
    lines.append("\n<b>EMA индикаторы:</b>")
    for period in [8, 54, 78, 200]:
        ema_key = f"EMA_{period}"
        if ema_key in emas and emas[ema_key] is not None:
            ema_value = emas[ema_key]
            if current_price > ema_value:
                lines.append(f"EMA-{period}: {ema_value:.6f} ▲")
            elif current_price < ema_value:
                lines.append(f"EMA-{period}: {ema_value:.6f} ▼")
            else:
                lines.append(f"EMA-{period}: {ema_value:.6f} ●")
    
    return "\n".join(lines)

async def render_and_send(session: aiohttp.ClientSession, chat_id: str, sym: str, tf: str) -> None:
    # 1) Котировки
    candles = await fb.fetch_kline(session, sym, tf, 250)

    # 2) Уровни
    lv = st.calculate_levels(candles, sym, tf)
    
    if not lv:
        print(f"[FORCE][ERROR] Не удалось рассчитать уровни для {sym} {tf}")
        return

    # 3) RSI последнего окна
    try:
        rsi_val = st.calculate_rsi(candles)
        if rsi_val is None:
            rsi_val = 50.0
    except Exception as e:
        print(f"[FORCE][WARN] Ошибка RSI для {sym} {tf}: {e}")
        rsi_val = 50.0

    # 4) EMA
    emas = st.calculate_all_emas(candles)
    
    # 5) Δ% по базовой свече
    base_ts = lv.get("_base_ts", 0)
    if base_ts > 0 and candles:
        # Находим базовую свечу по timestamp
        base_candle = None
        for candle in candles:
            if int(candle.get("ts", 0)) == base_ts:
                base_candle = candle
                break
        
        if base_candle:
            base_open = float(base_candle.get("open", 0))
            base_close = float(base_candle.get("close", 0))
            if base_open != 0:
                pct_move = abs((base_close - base_open) / base_open) * 100.0
            else:
                pct_move = 0.0
        else:
            pct_move = 0.0
    else:
        pct_move = 0.0

    # 6) Рендер PNG
    try:
        img_path = os.path.join(OUT_DIR, f"{sym}_{tf}_force.png")
        ch.plot_png(candles, lv, img_path, title=f"{sym} {tf} Force Push")
        
        if not os.path.exists(img_path) or os.path.getsize(img_path) < 1000:
            print(f"[FORCE][ERROR] Не удалось создать PNG для {sym} {tf}")
            return
    except Exception as e:
        print(f"[FORCE][ERROR] Ошибка построения графика {sym} {tf}: {e}")
        return

    # 6) Подпись и отправка
    current_price = float(candles[-1].get("close", 0)) if candles else 0
    caption = caption_from_levels(sym, tf, lv, rsi_val, pct_move, emas, current_price, candles[-1] if candles else {})
    
    tgq = tg.TGQ()
    try:
        await tgq.send_text(f"🔄 <b>FORCE PUSH: {sym} {tf}</b>")
        await tgq.send_photo(img_path, caption)
        print(f"[FORCE] sent {sym} {tf}")
    except Exception as e:
        print(f"[FORCE][ERROR] Ошибка отправки в Telegram {sym} {tf}: {e}")

async def main():
    load_dotenv()
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is not set")

    async with aiohttp.ClientSession() as s:
        # Принудительно обрабатываем все пары по очереди
        for sym, tf in PAIRS:
            try:
                await render_and_send(s, chat_id, sym, tf)
                await asyncio.sleep(1)  # Задержка между парами
            except Exception as e:
                print(f"[FORCE][ERROR] {sym} {tf}: {e}")

if __name__ == "__main__":
    asyncio.run(main())