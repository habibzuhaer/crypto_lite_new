# -*- coding: utf-8 -*-
from __future__ import annotations

import os, asyncio, logging, time, sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from dotenv import load_dotenv
import aiohttp

# Загружаем переменные окружения
load_dotenv()

# Получаем переменные окружения
TG_TOKEN = os.getenv('TG_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')

if not TG_TOKEN:
    logging.error("TG_TOKEN не установлен в переменных окружения")
    sys.exit(1)

if not TG_CHAT_ID:
    logging.error("TG_CHAT_ID не установлен в переменных окружения")
    sys.exit(1)

# Настройка логгера СРАЗУ, чтобы видеть все ошибки
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)

# Теперь импортируем остальные модули
try:
    from strategy_levels import (
        calculate_levels, 
        pick_biggest_candle,
        calculate_rsi,
        calculate_all_emas,
        ema_trend_analysis,
        detect_patterns,
        calculate_levels_for_candle
    )
    from charting import plot_png
    from tg import TelegramBot
    from trend_detector import analyze_trend
    from futures_bybit import fetch_kline
    
    # MarginZone модули
    try:
        from margin_zone_engine import find_margin_zones
        MARGINZONE_AVAILABLE = True
        logging.info("✅ MarginZone модули загружены")
    except ImportError as e:
        logging.warning(f"MarginZone модули не доступны: {e}")
        MARGINZONE_AVAILABLE = False
        
except ImportError as e:
    logging.error(f"❌ Ошибка импорта модулей: {e}")
    import traceback
    logging.error(traceback.format_exc())
    sys.exit(1)

OUT_DIR = str(Path("out").resolve())
Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

# ============================================================================
# КОНФИГУРАЦИЯ СИСТЕМЫ
# ============================================================================

# Группы таймфреймов согласно требованиям
MTF_GROUP = ["5m", "15m"]   # Среднесрочные: только уровни
STF_GROUP = ["1h", "4h"]    # Краткосрочные: уровни, зоны и совпадения

# СЛОВАРЬ ПАР И ТАЙМФРЕЙМОВ
SYMBOLS_TFS = {
    "GRTUSDT": ["5m", "1h"],
    "LINKUSDT": ["15m", "4h"],
    "ADAUSDT": ["15m", "1h"],
    "INJUSDT": ["15m", "1h"],
}

TF_MIN = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}

# Параметры для маржинальных зон
ZONES_ATR_MULTIPLIER = 1.8
ZONES_CONSOLIDATION_BARS = 5
ZONES_MIN_WIDTH_PERCENT = 0.05
COLLISION_THRESHOLD_PERCENT = 0.105  # Порог совпадения 0.105%

# ============================================================================
# ГЛОБАЛЬНЫЕ СОСТОЯНИЯ
# ============================================================================

# Состояния для уровней, зон и совпадений
_last_state: Dict[str, str] = {}
_last_zones_state: Dict[str, str] = {}
_last_collisions_state: Dict[str, str] = {}
_last_sent_candle_ts: Dict[str, int] = {}
_last_price: Dict[str, float] = {}
_last_banner_ts: float = 0.0

_break_mode: Dict[str, str] = {}
_break_count: Dict[str, int] = {}
_break_latched: Dict[str, bool] = {}
_latched_on_ts: Dict[str, int] = {}
_wait_new_candle: Dict[str, bool] = {}

# Для отслеживания пробоев
_last_breakout_time: Dict[str, int] = {}
_current_levels: Dict[str, Dict[str, float]] = {}

# Для хранения уровней, зон и совпадений
_levels_data: Dict[str, List[float]] = {}
_zones_data: Dict[str, List[Dict]] = {}
_collisions_data: Dict[str, List[Dict]] = {}

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def _key(symbol: str, tf: str) -> str:
    return f"{symbol}|{tf}"

def _state_signature(levels: Dict[str, float]) -> str:
    """Создает уникальную сигнатуру для уровней."""
    if not levels:
        return ""
    return "|".join(
        f"{levels.get(k, 0):.8f}"
        for k in ("X", "A", "C", "D", "F", "Y")
    ) + f"|base={levels.get('_base_ts', 0)}"

def _zones_signature(zones: List[Dict]) -> str:
    """Создает уникальную сигнатуру для маржинальных зон."""
    if not zones:
        return "no_zones"
    return "|".join(
        f"{zone.get('low', 0):.8f}-{zone.get('high', 0):.8f}"
        for zone in zones[:5]  # Берем первые 5 зон
    )

def _collisions_signature(collisions: List[Dict]) -> str:
    """Создает уникальную сигнатуру для совпадений."""
    if not collisions:
        return "no_collisions"
    return "|".join(
        f"{collision.get('level', 0):.8f}-{collision.get('zone_low', 0):.8f}-{collision.get('zone_high', 0):.8f}"
        for collision in collisions[:5]  # Берем первые 5 совпадений
    )

def _bars_24h(tf: str) -> int:
    """Количество баров за 24 часа для данного ТФ."""
    return max(1, (24 * 60) // TF_MIN.get(tf, 5))

def _ts_to_human_str(ts_ms: int) -> str:
    """Преобразует timestamp в читаемое время с указанием дня недели на русском."""
    if ts_ms <= 0:
        return "N/A"
    
    t = time.localtime(ts_ms // 1000)
    days_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    day_of_week = days_ru[t.tm_wday]
    
    return time.strftime(f"%d.%m.%Y {day_of_week} %H:%M", t)

def _get_candle_time_range(candle: Dict, tf: str) -> Tuple[str, str]:
    """Возвращает время открытия и закрытия свечи."""
    ts_ms = int(candle.get("ts", 0))
    if ts_ms <= 0:
        return "N/A", "N/A"
    
    open_time = _ts_to_human_str(ts_ms)
    
    tf_duration_ms = {
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000
    }
    
    close_ts = ts_ms + tf_duration_ms.get(tf, 60 * 60 * 1000)
    close_time = _ts_to_human_str(close_ts)
    
    return open_time, close_time

def _rsi_tag(rsi: Optional[float]) -> str:
    """Форматирует RSI с эмодзи."""
    if rsi is None:
        return "—"
    if rsi >= 70:
        return f"{rsi:.1f} 🔴"
    if rsi <= 30:
        return f"{rsi:.1f} 🟢"
    return f"{rsi:.1f} 🟡"

def _format_ema_value(price: float, ema_value: Optional[float]) -> str:
    """Форматирует значение EMA с указанием положения цены."""
    if ema_value is None:
        return "—"
    
    diff = price - ema_value
    diff_percent = (diff / ema_value * 100) if ema_value != 0 else 0
    
    if diff > 0:
        return f"{ema_value:.6f} ▲ (+{abs(diff_percent):.2f}%)"
    elif diff < 0:
        return f"{ema_value:.6f} ▼ ({diff_percent:.2f}%)"
    else:
        return f"{ema_value:.6f} ● (0.00%)"

def _format_caption(
    symbol: str, 
    tf: str, 
    candles: List[Dict], 
    levels: Dict[str, float], 
    rsi14: Optional[float],
    emas: Dict[str, Optional[float]],
    ema_analysis: Dict[str, any],
    pats: List[str], 
    trend_info: Optional[Dict]
) -> str:
    """Формирует подпись для Telegram с улучшенным форматированием."""
    if not candles:
        return f"❌ Нет данных для {symbol} {tf}"
    
    c = candles[-1]
    price = float(c.get("close", 0.0))
    
    open_time, close_time = _get_candle_time_range(c, tf)
    
    main_levels = ["X", "F", "A", "C", "D", "Y"]
    level_lines = []
    for k in main_levels:
        if k in levels:
            level_lines.append(f"{k}: {levels[k]:.6f}")
    
    ema_display = []
    for period in [8, 54, 78, 200]:
        ema_key = f"EMA_{period}"
        if ema_key in emas and emas[ema_key] is not None:
            ema_display.append(f"EMA-{period}: {_format_ema_value(price, emas[ema_key])}")
    
    lines = [
        f"📈 #{symbol} • Таймфрейм: {tf}",
        f"💰 Цена: {price:.6f}",
        f"🕒 Время свечи: {open_time} - {close_time}",
        f"📊 Проанализировано: {len(candles)} свечей",
    ]
    
    if "_base_ts" in levels:
        base_time = _ts_to_human_str(int(levels["_base_ts"]))
        lines.append(f"🎯 Базовая свеча: {base_time}")
    
    if level_lines:
        lines.append("\n🎯 Ключевые уровни:")
        for i in range(0, len(level_lines), 2):
            if i + 1 < len(level_lines):
                lines.append(f"• {level_lines[i]} | {level_lines[i+1]}")
            else:
                lines.append(f"• {level_lines[i]}")
    
    if ema_display:
        lines.append("\n📊 EMA индикаторы:")
        for ema_line in ema_display:
            lines.append(f"• {ema_line}")
        
        if ema_analysis and "trend" in ema_analysis and ema_analysis["trend"] != "неопределён":
            trend_emoji = {
                "сильный бычий": "📈📈",
                "бычий": "📈",
                "слабый бычий": "↗️",
                "боковик": "➡️",
                "слабый медвежий": "↘️",
                "медвежий": "📉",
                "сильный медвежий": "📉📉"
            }.get(ema_analysis["trend"], "➖")
            
            lines.append(f"\n🎯 Тренд по EMA: {trend_emoji} {ema_analysis['trend']}")
            lines.append(f"Сила тренда: {ema_analysis.get('strength', 0)}%")
            
            if ema_analysis.get("signals"):
                signals_text = ", ".join(ema_analysis["signals"][:3])
                lines.append(f"📶 Сигналы: {signals_text}")
    
    if pats:
        lines.append(f"\n🎯 Паттерны:")
        for pat in pats:
            lines.append(f"• {pat}")
    
    lines.append(f"\n📊 RSI14: {_rsi_tag(rsi14)}")
    
    if trend_info and trend_info.get("trend") != "neutral":
        trend_name = {"long": "📈 Бычий", "short": "📉 Медвежий"}.get(trend_info["trend"], "➖ Нейтральный")
        conf = trend_info.get("confidence", 0) * 100
        lines.append(f"🚀 Общий тренд: {trend_name} ({conf:.0f}%)")
    
    return "\n".join(lines)

def check_collisions(levels: List[float], zones: List[Dict], current_price: float) -> List[Dict]:
    """
    Проверяет совпадения уровней с маржинальными зонами.
    Возвращает список словарей с информацией о совпадениях.
    """
    collisions = []
    
    if not levels or not zones:
        return collisions
    
    for level in levels:
        for zone in zones:
            zone_low = zone.get('low', 0)
            zone_high = zone.get('high', 0)
            
            # Расширяем границы зоны на порог совпадения (0.105%)
            lower_bound = zone_low * (1 - COLLISION_THRESHOLD_PERCENT / 100)
            upper_bound = zone_high * (1 + COLLISION_THRESHOLD_PERCENT / 100)
            
            # Проверяем, находится ли уровень внутри расширенной зоны
            if lower_bound <= level <= upper_bound:
                # Вычисляем расстояние до центра зоны
                zone_center = (zone_low + zone_high) / 2
                distance_to_center = abs(level - zone_center)
                distance_percent = (distance_to_center / zone_center) * 100 if zone_center != 0 else 0
                
                # Определяем позицию относительно зоны
                if level < zone_low:
                    position = "ниже зоны"
                elif level > zone_high:
                    position = "выше зоны"
                else:
                    position = "внутри зоны"
                
                collisions.append({
                    'level': level,
                    'zone_low': zone_low,
                    'zone_high': zone_high,
                    'zone_center': zone_center,
                    'distance_percent': distance_percent,
                    'position': position,
                    'zone_strength': zone.get('strength', 0)
                })
                break  # Каждый уровень может совпадать только с одной зоной
    
    return collisions

async def _fetch_with_retry(
    sess: aiohttp.ClientSession, 
    symbol: str, 
    tf: str, 
    limit: int = 250
) -> Optional[List[Dict]]:
    """Загрузка свечей с повторными попытками."""
    for attempt, delay in enumerate([0, 1, 2, 4, 8], start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            return await fetch_kline(sess, symbol, tf, limit=limit)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            logging.warning("[BYBIT] Попытка %s не удалась: %s", attempt, e)
            if attempt == 5:
                return None
    return None

def _check_breakout_and_recalculate(
    candles: List[Dict],
    current_levels: Dict[str, float],
    current_price: float,
    symbol: str,
    tf: str,
    key: str
) -> Tuple[Dict[str, float], bool, str]:
    """
    Проверяет пробой уровней X/Y и пересчитывает уровни при необходимости.
    """
    x = current_levels.get("X")
    y = current_levels.get("Y")
    
    if x is None or y is None:
        return current_levels, False, "Отсутствуют уровни X/Y"
    
    upper_level = max(x, y)
    lower_level = min(x, y)
    
    is_breakout = current_price > upper_level or current_price < lower_level
    
    if not is_breakout:
        return current_levels, False, "Цена в пределах структуры"
    
    last_breakout = _last_breakout_time.get(key, 0)
    current_time = int(time.time() * 1000)
    cooldown = 5 * 60 * 1000
    
    if current_time - last_breakout < cooldown:
        remaining = (cooldown - (current_time - last_breakout)) // 1000
        return current_levels, False, f"Кулдаун активен ({remaining} сек)"
    
    if len(candles) < 50:
        return current_levels, True, f"ПРОБОЙ! Недостаточно данных для поиска новой структуры (только {len(candles)} свечей)"
    
    logging.info(f"[BREAKOUT] Пробой структуры {symbol}/{tf}: цена={current_price:.6f}, X={x:.6f}, Y={y:.6f}")
    
    min_lookback = 190
    lookback = min_lookback if len(candles) >= min_lookback else len(candles)
    
    search_start = -lookback
    search_end = -5 if len(candles) > 5 else None
    search_candles = candles[search_start:search_end] if search_end else candles[search_start:]
    
    if not search_candles:
        search_candles = candles[-lookback:]
    
    logging.info(f"[BREAKOUT] Поиск в {len(search_candles)} свечах для {symbol}/{tf}")
    
    new_base = pick_biggest_candle(search_candles)
    if not new_base:
        new_base = pick_biggest_candle(candles[-100:]) if len(candles) >= 100 else pick_biggest_candle(candles)
    
    if not new_base:
        return current_levels, True, f"ПРОБОЙ! Не удалось найти новую базовую свечу для {symbol}/{tf}"
    
    old_base_ts = current_levels.get("_base_ts")
    same_base = False
    
    if old_base_ts and new_base.get("ts") == old_base_ts:
        same_base = True
        new_levels = current_levels
        logging.info(f"[BREAKOUT] Базовая свеча та же для {symbol}/{tf}")
    else:
        new_levels = calculate_levels_for_candle(new_base)
        new_levels["_base_ts"] = new_base["ts"]
        new_levels["_base_open"] = new_base["open"]
        new_levels["_base_high"] = new_base["high"]
        new_levels["_base_low"] = new_base["low"]
        new_levels["_base_close"] = new_base["close"]
    
    _last_breakout_time[key] = current_time
    
    direction = "ВВЕРХ" if current_price > upper_level else "ВНИЗ"
    base_status = " (та же базовая свеча)" if same_base else " (новая базовая свеча)"
    
    if same_base:
        description = (
            f"🚨 ПРОБОЙ СТРУКТУРЫ {symbol} {tf}{base_status}\n"
            f"Цена: {current_price:.6f} ({direction})\n"
            f"Выход за: {(upper_level if direction == 'ВВЕРХ' else lower_level):.6f}\n"
            f"Базовая свеча осталась прежней\n"
            f"Текущие уровни: X={x:.6f}, Y={y:.6f}"
        )
    else:
        description = (
            f"🚨 ПРОБОЙ СТРУКТУРЫ {symbol} {tf}{base_status}\n"
            f"Цена: {current_price:.6f} ({direction})\n"
            f"Выход за: {(upper_level if direction == 'ВВЕРХ' else lower_level):.6f}\n"
            f"Старые границы: {lower_level:.6f} - {upper_level:.6f}\n"
            f"Новые уровни: X={new_levels.get('X', 0):.6f}, Y={new_levels.get('Y', 0):.6f}"
        )
    
    logging.info(f"[BREAKOUT] {'Базовая свеча та же' if same_base else 'Новые уровни'} для {symbol}/{tf}")
    
    return new_levels, True, description

def _update_break_state(
    key: str, 
    close_price: float, 
    levels: Dict[str, float], 
    curr_ts: int
) -> None:
    """Обновляет состояние пробоя уровней."""
    x = levels.get("X")
    y = levels.get("Y")
    
    if x is None or y is None:
        _break_mode[key] = "inside"
        _break_count[key] = 0
        _break_latched[key] = False
        _wait_new_candle[key] = False
        _latched_on_ts[key] = -1
        return
    
    if close_price > float(y):
        mode = "aboveY"
    elif close_price < float(x):
        mode = "belowX"
    else:
        mode = "inside"
    
    prev_mode = _break_mode.get(key, "inside")
    
    if mode == "inside":
        _break_mode[key] = "inside"
        _break_count[key] = 0
        _break_latched[key] = False
        _wait_new_candle[key] = False
        _latched_on_ts[key] = -1
        return
    
    if mode == prev_mode:
        _break_count[key] = _break_count.get(key, 0) + 1
    else:
        _break_mode[key] = mode
        _break_count[key] = 1
    
    if _break_count[key] >= 6:
        if not _break_latched.get(key, False):
            _latched_on_ts[key] = curr_ts
        _break_latched[key] = True
        _wait_new_candle[key] = True

async def _send_levels_message(
    tg: TelegramBot,
    symbol: str,
    tf: str,
    candles: List[Dict],
    current_levels: Dict[str, float],
    current_price: float,
    rsi14: Optional[float],
    emas: Dict[str, Optional[float]],
    ema_analysis: Dict[str, any],
    pats: List[str],
    trend_info: Optional[Dict],
    breakout_description: str = ""
) -> bool:
    """Отправляет сообщение с уровнями и графиком."""
    try:
        # Генерируем график
        img_path = os.path.join(OUT_DIR, f"{symbol}_{tf}_{int(time.time())}.png")
        
        title = f"{symbol} {tf}"
        if rsi14:
            title += f"  RSI={rsi14:.1f}"
        
        os.makedirs(os.path.dirname(img_path), exist_ok=True)
        
        plot_png(candles, current_levels, img_path, title=title)
        
        if not os.path.exists(img_path) or os.path.getsize(img_path) < 1000:
            logging.error("[CHART] Не удалось создать график для %s/%s", symbol, tf)
            return False
        
        # Формируем подпись
        cap = _format_caption(symbol, tf, candles, current_levels, rsi14, emas, ema_analysis, pats, trend_info)
        
        if breakout_description and "ПРОБОЙ" in breakout_description:
            cap = f"🚨 {breakout_description}\n\n{cap}"
        
        logging.info(f"Отправка фото для {symbol}/{tf}")
        
        ok = await tg.send_photo(img_path, cap)
        
        return ok
        
    except Exception as e:
        logging.error("[CHART] Ошибка построения графика: %s", e)
        return False

async def _send_zones_message(
    tg: TelegramBot,
    symbol: str,
    tf: str,
    zones: List[Dict],
    current_price: float
) -> bool:
    """Отправляет сообщение о маржинальных зонах."""
    if not zones:
        return False
    
    # Сортируем зоны по средней точке
    sorted_zones = sorted(zones, key=lambda z: (z.get('high', 0) + z.get('low', 0)) / 2)
    
    message = f"""
🎯 *Маржинальные зоны {symbol} | {tf}*
──────────────────────
💰 Текущая цена: `{current_price:.6f}`

📏 *Обнаруженные зоны ликвидности:*
"""
    
    for i, zone in enumerate(sorted_zones, 1):
        zone_low = zone.get('low', 0)
        zone_high = zone.get('high', 0)
        zone_mid = (zone_low + zone_high) / 2
        zone_width_percent = ((zone_high - zone_low) / zone_mid) * 100
        
        # Определяем положение зоны относительно текущей цены
        if current_price > zone_high:
            position = "🔴 Выше цены"
        elif current_price < zone_low:
            position = "🟢 Ниже цены"
        else:
            position = "🟡 Цена ВНУТРИ зоны!"
        
        message += f"""
{i}. *Диапазон:* `{zone_low:.6f}` - `{zone_high:.6f}`
   *Средняя:* `{zone_mid:.6f}`
   *Ширина:* {zone_width_percent:.2f}%
   *Положение:* {position}
"""
    
    message += f"""
──────────────────────
📊 Всего зон: {len(zones)}
⏰ {time.strftime('%H:%M:%S')}
"""
    
    return await tg.send_message(message)

async def _send_collisions_message(
    tg: TelegramBot,
    symbol: str,
    tf: str,
    collisions: List[Dict],
    current_price: float
) -> bool:
    """Отправляет специальное сообщение о совпадениях с желтым треугольником."""
    if not collisions:
        return False
    
    message = f"""
⚠️ *СОВПАДЕНИЕ УРОВНЕЙ И ЗОН! {symbol} | {tf}*
──────────────────────
💰 Текущая цена: `{current_price:.6f}`

🎯 *Обнаруженные совпадения:*
"""
    
    for i, collision in enumerate(collisions, 1):
        level = collision.get('level', 0)
        zone_low = collision.get('zone_low', 0)
        zone_high = collision.get('zone_high', 0)
        zone_center = collision.get('zone_center', 0)
        position = collision.get('position', '')
        distance_percent = collision.get('distance_percent', 0)
        
        message += f"""
{i}. *Уровень:* `{level:.6f}`
   *Зона:* `{zone_low:.6f}` - `{zone_high:.6f}`
   *Позиция:* {position}
   *Расстояние до центра:* {distance_percent:.3f}%
   *Сила зоны:* {collision.get('zone_strength', 0):.1f}
"""
    
    message += f"""
──────────────────────
💡 *Интерпретация:*
Совпадение технических уровней с маржинальными зонами 
указывает на области повышенной ликвидности, 
где вероятны сильные движения цены.

⏰ {time.strftime('%H:%M:%S')}
"""
    
    return await tg.send_message(message)

async def run_symbol_tf(
    sess: aiohttp.ClientSession, 
    tg: TelegramBot,
    symbol: str, 
    tf: str
) -> bool:
    """Обрабатывает одну пару символ/ТФ."""
    key = _key(symbol, tf)
    sent_messages = 0
    
    try:
        # 1. Загружаем свечи
        candles = await _fetch_with_retry(sess, symbol, tf, 250)
        if not candles:
            logging.warning("[WARN] Нет свечей для %s/%s", symbol, tf)
            return False
        
        c_last = candles[-1]
        curr_price = float(c_last.get("close", 0))
        curr_ts = int(c_last.get("ts", 0))
        
        # 2. Проверяем, не отправляли ли уже эту свечу (для уровней)
        if _last_sent_candle_ts.get(key) == curr_ts:
            # Проверяем только для уровней, зоны могут обновляться независимо
            pass
        
        # 3. Получаем текущие уровни или рассчитываем новые
        current_levels = _current_levels.get(key)
        need_send_message = False
        breakout_description = ""
        breakout_detected = False
        
        if not current_levels:
            current_levels = calculate_levels(candles, symbol, tf, use_biggest_from_last=240)
            if not current_levels:
                logging.warning("[WARN] Не удалось расчитать уровни для %s/%s", symbol, tf)
                return False
            _current_levels[key] = current_levels
            need_send_message = True
        else:
            new_levels, should_send, description = _check_breakout_and_recalculate(
                candles, current_levels, curr_price, symbol, tf, key
            )
            
            breakout_description = description
            breakout_detected = "ПРОБОЙ" in description
            
            if breakout_detected:
                if new_levels and new_levels != current_levels:
                    current_levels = new_levels
                    _current_levels[key] = current_levels
                
                need_send_message = True
                
                _break_mode[key] = "inside"
                _break_count[key] = 0
                _break_latched[key] = False
                _wait_new_candle[key] = False
                _latched_on_ts[key] = -1
        
        # 4. Добавляем timestamp базовой свечи
        base = pick_biggest_candle(candles[-240:])
        if base and "ts" in base:
            current_levels["_base_ts"] = base["ts"]
        
        # 5. Определяем паттерны
        lookback = min(len(candles), _bars_24h(tf))
        pats = detect_patterns(candles[-lookback:])
        
        # 6. Рассчитываем RSI
        rsi14 = calculate_rsi(candles)
        
        # 7. Рассчитываем EMA
        emas = calculate_all_emas(candles)
        ema_analysis = ema_trend_analysis(emas, curr_price)
        
        # 8. Анализ тренда
        trend_info = None
        if tf in ["5m", "15m", "1h"]:
            tf_map = {"5m": "15m", "15m": "1h", "1h": "4h", "4h": "4h"}
            tf_higher = tf_map.get(tf, tf)
            
            candles_higher = await _fetch_with_retry(sess, symbol, tf_higher, 120)
            if candles_higher:
                try:
                    trend_info = analyze_trend(candles, candles_higher)
                except Exception as e:
                    logging.warning("[TREND] Ошибка анализа тренда: %s", e)
                    trend_info = None
        
        # 9. Обновляем состояние пробоя
        _update_break_state(key, curr_price, current_levels, curr_ts)
        
        latched = _break_latched.get(key, False)
        latched_ts = _latched_on_ts.get(key, -1)
        need_new = _wait_new_candle.get(key, False)
        
        # 10. Проверяем условия для отправки уровней
        should_send_levels = (
            latched and 
            need_new and 
            curr_ts != latched_ts and 
            curr_ts > latched_ts >= 0
        ) or need_send_message
        
        # 11. Проверяем, не отправляли ли уже эти уровни
        state = _state_signature(current_levels)
        if _last_state.get(key) == state and not need_send_message:
            # Уровни не изменились
            should_send_levels = False
        else:
            # Сохраняем уровни
            level_values = [current_levels.get(k) for k in ["X", "A", "C", "D", "F", "Y"] 
                           if current_levels.get(k) is not None]
            _levels_data[key] = level_values
        
        # 12. ОБРАБОТКА ДЛЯ РАЗНЫХ ГРУПП ТАЙМФРЕЙМОВ
        if tf in MTF_GROUP:
            # ТОЛЬКО для MTF: отправляем только уровни
            if should_send_levels:
                ok = await _send_levels_message(
                    tg, symbol, tf, candles, current_levels, curr_price,
                    rsi14, emas, ema_analysis, pats, trend_info, breakout_description
                )
                if ok:
                    _last_state[key] = state
                    _last_sent_candle_ts[key] = curr_ts
                    _last_price[key] = curr_price
                    _wait_new_candle[key] = False
                    sent_messages += 1
                    logging.info("[MTF] Уровни отправлены для %s/%s", symbol, tf)
        
        elif tf in STF_GROUP:
            # ДЛЯ STF: уровни + маржинальные зоны + совпадения
            
            # A) Получаем маржинальные зоны (только для STF)
            current_zones = []
            if MARGINZONE_AVAILABLE:
                try:
                    current_zones = find_margin_zones(
                        candles=candles,
                        atr_multiplier=ZONES_ATR_MULTIPLIER,
                        consolidation_bars=ZONES_CONSOLIDATION_BARS,
                        min_zone_width_percent=ZONES_MIN_WIDTH_PERCENT
                    )
                    _zones_data[key] = current_zones
                except Exception as e:
                    logging.error(f"[MarginZone] Ошибка получения зон {symbol}/{tf}: {e}")
            
            # B) Проверяем совпадения уровней с зонами
            current_collisions = []
            if current_zones and _levels_data.get(key):
                current_collisions = check_collisions(_levels_data[key], current_zones, curr_price)
                _collisions_data[key] = current_collisions
            
            # C) Отправляем сообщения для STF
            
            # 1. Отправляем уровни (если нужно)
            if should_send_levels:
                ok = await _send_levels_message(
                    tg, symbol, tf, candles, current_levels, curr_price,
                    rsi14, emas, ema_analysis, pats, trend_info, breakout_description
                )
                if ok:
                    _last_state[key] = state
                    _last_sent_candle_ts[key] = curr_ts
                    _last_price[key] = curr_price
                    _wait_new_candle[key] = False
                    sent_messages += 1
                    logging.info("[STF] Уровни отправлены для %s/%s", symbol, tf)
            
            # 2. Отправляем маржинальные зоны (если есть и изменились)
            zones_state = _zones_signature(current_zones)
            if current_zones and _last_zones_state.get(key) != zones_state:
                ok = await _send_zones_message(tg, symbol, tf, current_zones, curr_price)
                if ok:
                    _last_zones_state[key] = zones_state
                    sent_messages += 1
                    logging.info("[STF] Зоны отправлены для %s/%s", symbol, tf)
            
            # 3. Отправляем совпадения (если есть и изменились)
            collisions_state = _collisions_signature(current_collisions)
            if current_collisions and _last_collisions_state.get(key) != collisions_state:
                ok = await _send_collisions_message(tg, symbol, tf, current_collisions, curr_price)
                if ok:
                    _last_collisions_state[key] = collisions_state
                    sent_messages += 1
                    logging.info("[STF] Совпадения отправлены для %s/%s", symbol, tf)
        
        # Обновляем цену
        _last_price[key] = curr_price
        
        return sent_messages > 0
        
    except Exception as e:
        logging.error("[ERROR] %s/%s: %s", symbol, tf, e)
        import traceback
        logging.error(traceback.format_exc())
        return False

async def main_loop() -> None:
    """Основной цикл бота."""
    global _last_banner_ts
    
    logging.info("=" * 60)
    logging.info("🚀 Бот запускается...")
    logging.info(f"Python: {sys.version}")
    logging.info(f"Working Directory: {os.getcwd()}")
    logging.info(f"MarginZone доступен: {MARGINZONE_AVAILABLE}")
    logging.info(f"MTF таймфреймы: {MTF_GROUP}")
    logging.info(f"STF таймфреймы: {STF_GROUP}")
    logging.info("=" * 60)
    
    # Инициализируем Telegram бота
    try:
        tg = TelegramBot(TG_TOKEN, TG_CHAT_ID)
        logging.info("✅ Telegram бот инициализирован")
    except Exception as e:
        logging.error(f"❌ Ошибка инициализации Telegram бота: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return
    
    # Инициализируем HTTP сессию
    try:
        sess = aiohttp.ClientSession()
        logging.info("✅ HTTP сессия создана")
    except Exception as e:
        logging.error(f"❌ Ошибка создания HTTP сессии: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return
    
    TF_SLEEP = 60
    error_count = 0
    max_errors = 5
    
    logging.info("🚀 Основной цикл начат")
    
    try:
        while error_count < max_errors:
            sent_count = 0
            start_time = time.time()
            
            try:
                for symbol, tfs in SYMBOLS_TFS.items():
                    for tf in tfs:
                        try:
                            if await run_symbol_tf(sess, tg, symbol, tf):
                                sent_count += 1
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            logging.error(f"Ошибка обработки {symbol}/{tf}: {e}")
                            error_count += 1
                
                now = time.time()
                if sent_count > 0 and (now - _last_banner_ts) >= 1800:
                    banner_text = f"""📊 <b>Market Monitor Active</b>
Обработано пар: {len(SYMBOLS_TFS)}
MTF таймфреймы: {', '.join(MTF_GROUP)}
STF таймфреймы: {', '.join(STF_GROUP)}
Отправлено сигналов: {sent_count}
MarginZone активен: {'Да' if MARGINZONE_AVAILABLE else 'Нет'}"""
                    
                    if await tg.send_message(banner_text):
                        _last_banner_ts = now
                        logging.info("[BANNER] Отправлен баннер")
                
                # Сброс счетчика ошибок при успешной итерации
                if sent_count > 0:
                    error_count = 0
                
                loop_time = time.time() - start_time
                if loop_time > TF_SLEEP:
                    logging.warning("[PERF] Цикл занял %.2fс (дольше чем интервал %dс)", 
                                  loop_time, TF_SLEEP)
                
                sleep_time = max(1, TF_SLEEP - loop_time)
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logging.error(f"❌ Ошибка в основном цикле: {e}")
                import traceback
                logging.error(traceback.format_exc())
                error_count += 1
                await asyncio.sleep(30)
        
        logging.error(f"🛑 Достигнут максимум ошибок ({max_errors}), бот останавливается")
        
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("🛑 Бот остановлен по запросу")
    except Exception as e:
        logging.error(f"❌ Критическая ошибка: {e}")
        import traceback
        logging.error(traceback.format_exc())
    finally:
        # Корректное завершение
        try:
            await sess.close()
            logging.info("✅ HTTP сессия закрыта")
        except:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logging.error(f"❌ Критическая ошибка при запуске: {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)