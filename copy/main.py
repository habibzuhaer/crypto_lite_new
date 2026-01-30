# -*- coding: utf-8 -*-
from __future__ import annotations

import os, asyncio, logging, time, sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from dotenv import load_dotenv
import aiohttp

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
from tg import TGQ, kb_main
from engine_paper import place_limit, place_tp, place_sl, cancel, positions, get_balance
from trend_detector import analyze_trend
from futures_bybit import fetch_kline

load_dotenv()
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)

OUT_DIR = str(Path("out").resolve())
Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

# СЛОВАРЬ ПАР И ТАЙМФРЕЙМОВ
SYMBOLS_TFS = {
    "GRTUSDT": ["5m", "1h"],
    "LINKUSDT": ["15m", "4h"],
    "ADAUSDT": ["15m", "1h"],
    "INJUSDT": ["15m", "1h"],
}

# Времена обновления для каждого ТФ в секундах
TF_UPDATE_INTERVALS = {
    "5m": 60,     # Каждую минуту (5m свеча)
    "15m": 300,   # Каждые 5 минут (15m свеча)
    "1h": 900,    # Каждые 15 минут (1h свеча)
    "4h": 3600,   # Каждый час (4h свеча)
}

# Глобальные состояния
_last_state: Dict[str, str] = {}
_last_sent_candle_ts: Dict[str, int] = {}
_last_price: Dict[str, float] = {}
_last_banner_ts: float = 0.0
_last_check_time: Dict[str, float] = {}  # Время последней проверки для каждой пары

# Для отслеживания пробоев
_last_breakout_time: Dict[str, int] = {}
_current_levels: Dict[str, Dict[str, float]] = {}
_breakout_counts: Dict[str, int] = {}  # Счетчики пробоев для каждого ключа

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

def _bars_24h(tf: str) -> int:
    """Количество баров за 24 часа для данного ТФ."""
    tf_minutes = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}
    return max(1, (24 * 60) // tf_minutes.get(tf, 5))

def _ts_to_human_str(ts_ms: int) -> str:
    """Преобразует timestamp в читаемое время."""
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
    """Форматирует значение EMA."""
    if ema_value is None:
        return "—"
    
    diff = price - ema_value
    diff_percent = (diff / ema_value * 100) if ema_value != 0 else 0
    
    if diff > 0:
        return f"{ema_value:.6f} (+{diff_percent:.2f}%) ▲"
    elif diff < 0:
        return f"{ema_value:.6f} ({diff_percent:.2f}%) ▼"
    else:
        return f"{ema_value:.6f} (0.00%) ●"

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
    """Формирует подпись для Telegram."""
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
        f"🟢 <b>#{symbol}</b> ТФ: <b>{tf}</b>",
        f"Цена: <b>{price:.6f}</b>",
        f"Время свечи: {open_time}",
        f"Анализ: последние {len(candles)} свечей",
    ]
    
    if "_base_ts" in levels:
        base_time = _ts_to_human_str(int(levels["_base_ts"]))
        lines.append(f"Базовая свеча: <b>{base_time}</b>")
    
    if level_lines:
        lines.append("\n📊 <b>Основные уровни:</b>")
        lines.extend(level_lines)
    
    if ema_display:
        lines.append("\n📈 <b>EMA индикаторы:</b>")
        lines.extend(ema_display)
        
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
            
            lines.append(f"\n🎯 <b>Тренд по EMA:</b> {trend_emoji} {ema_analysis['trend']} ({ema_analysis.get('strength', 0)}%)")
    
    if pats:
        lines.append(f"\n🎯 <b>Паттерны:</b> {', '.join(pats)}")
    
    lines.append(f"\n📈 <b>RSI14:</b> {_rsi_tag(rsi14)}")
    
    if trend_info and trend_info.get("trend") != "neutral":
        trend_name = {"long": "📈 Бычий", "short": "📉 Медвежий"}.get(trend_info["trend"], "➖ Нейтральный")
        conf = trend_info.get("confidence", 0) * 100
        lines.append(f"\n🚀 <b>Тренд:</b> {trend_name} ({conf:.0f}%)")
    
    return "\n".join(lines)

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
            candles = await fetch_kline(sess, symbol, tf, limit=limit)
            if candles and len(candles) > 0:
                return candles
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
    
    Returns:
        (новые_уровни, нужно_ли_отправить_сообщение, описание_пробоя)
    """
    x = current_levels.get("X")
    y = current_levels.get("Y")
    
    if x is None or y is None:
        return current_levels, False, "Отсутствуют уровни X/Y"
    
    upper_level = max(x, y)
    lower_level = min(x, y)
    
    is_breakout = current_price > upper_level or current_price < lower_level
    
    if not is_breakout:
        return current_levels, False, ""
    
    # Кулдаун 5 минут для всех ТФ
    last_breakout = _last_breakout_time.get(key, 0)
    current_time = int(time.time() * 1000)
    cooldown = 5 * 60 * 1000  # 5 минут
    
    if current_time - last_breakout < cooldown:
        remaining = (cooldown - (current_time - last_breakout)) // 1000
        return current_levels, False, f"Кулдаун активен ({remaining} сек)"
    
    # Проверяем достаточность данных
    if len(candles) < 50:
        return current_levels, True, f"ПРОБОЙ! Недостаточно данных для поиска новой структуры (только {len(candles)} свечей)"
    
    logging.info(f"[BREAKOUT] Пробой структуры {symbol}/{tf}: цена={current_price:.6f}, X={x:.6f}, Y={y:.6f}")
    
    # Минимальное окно поиска 190 свечей
    min_lookback = 190
    lookback = min_lookback if len(candles) >= min_lookback else len(candles)
    
    # Ищем в последних N свечах, исключая последние 5 свечей
    search_start = -lookback
    search_end = -5 if len(candles) > 5 else None
    search_candles = candles[search_start:search_end] if search_end else candles[search_start:]
    
    if not search_candles:
        search_candles = candles[-lookback:]
    
    logging.info(f"[BREAKOUT] Поиск в {len(search_candles)} свечах для {symbol}/{tf}")
    
    # Ищем самую большую свечу
    new_base = pick_biggest_candle(search_candles)
    if not new_base:
        new_base = pick_biggest_candle(candles[-100:]) if len(candles) >= 100 else pick_biggest_candle(candles)
    
    if not new_base:
        return current_levels, True, f"ПРОБОЙ! Не удалось найти новую базовую свечу для {symbol}/{tf}"
    
    # Проверяем, не та же ли это базовая свеча
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
    
    # Обновляем время последнего пробоя и счетчик
    _last_breakout_time[key] = current_time
    _breakout_counts[key] = _breakout_counts.get(key, 0) + 1
    
    direction = "ВВЕРХ" if current_price > upper_level else "ВНИЗ"
    base_status = " (та же базовая свеча)" if same_base else " (новая базовая свеча)"
    
    if same_base:
        description = (
            f"🚨 ПРОБОЙ СТРУКТУРЫ #{_breakout_counts.get(key, 1)} {symbol} {tf}{base_status}\n"
            f"Цена: {current_price:.6f} ({direction})\n"
            f"Выход за: {upper_level:.6f if direction == 'ВВЕРХ' else lower_level:.6f}\n"
            f"Базовая свеча осталась прежней\n"
            f"Текущие уровни: X={x:.6f}, Y={y:.6f}"
        )
    else:
        description = (
            f"🚨 ПРОБОЙ СТРУКТУРЫ #{_breakout_counts.get(key, 1)} {symbol} {tf}{base_status}\n"
            f"Цена: {current_price:.6f} ({direction})\n"
            f"Выход за: {upper_level:.6f if direction == 'ВВЕРХ' else lower_level:.6f}\n"
            f"Старые границы: {lower_level:.6f} - {upper_level:.6f}\n"
            f"Новые уровни: X={new_levels.get('X'):.6f}, Y={new_levels.get('Y'):.6f}"
        )
    
    logging.info(f"[BREAKOUT] {'Базовая свеча та же' if same_base else 'Новые уровни'} для {symbol}/{tf}")
    
    # Всегда отправляем сообщение при пробое
    return new_levels, True, description

async def run_symbol_tf(
    sess: aiohttp.ClientSession, 
    tg: TGQ, 
    symbol: str, 
    tf: str
) -> bool:
    """Обрабатывает одну пару символ/ТФ в цикле."""
    key = _key(symbol, tf)
    
    try:
        # Проверяем, нужно ли обновлять этот ТФ
        current_time = time.time()
        last_check = _last_check_time.get(key, 0)
        update_interval = TF_UPDATE_INTERVALS.get(tf, 60)
        
        if current_time - last_check < update_interval:
            return False
        
        # Обновляем время последней проверки
        _last_check_time[key] = current_time
        
        # 1. Загружаем свечи
        candles = await _fetch_with_retry(sess, symbol, tf, 250)
        if not candles or len(candles) < 50:
            logging.warning("[WARN] Нет свечей или мало данных для %s/%s", symbol, tf)
            return False
        
        c_last = candles[-1]
        curr_price = float(c_last.get("close", 0))
        curr_ts = int(c_last.get("ts", 0))
        
        # 2. Проверяем, не отправляли ли уже эту свечу
        if _last_sent_candle_ts.get(key) == curr_ts:
            return False
        
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
        
        # 9. Проверяем, нужно ли отправлять сообщение
        # Отправляем регулярные обновления раз в N времени для каждого ТФ
        last_sent = _last_sent_candle_ts.get(key, 0)
        time_since_last = current_time - (last_sent / 1000 if last_sent > 0 else 0)
        
        # Интервалы отправки регулярных обновлений
        regular_update_intervals = {
            "5m": 300,    # 5 минут
            "15m": 900,   # 15 минут
            "1h": 3600,   # 1 час
            "4h": 14400,  # 4 часа
        }
        
        regular_interval = regular_update_intervals.get(tf, 900)
        need_regular_update = time_since_last > regular_interval
        
        should_send = need_send_message or need_regular_update or breakout_detected
        
        if not should_send:
            _last_price[key] = curr_price
            return False
        
        # 10. Проверяем, не отправляли ли уже эти уровни
        state = _state_signature(current_levels)
        if _last_state.get(key) == state and not breakout_detected and not need_regular_update:
            _last_price[key] = curr_price
            return False
        
        # 11. Генерируем график
        img_path = os.path.join(OUT_DIR, f"{symbol}_{tf}_{int(time.time())}.png")
        try:
            title = f"{symbol} {tf}"
            if rsi14:
                title += f"  RSI={rsi14:.1f}"
            
            if breakout_detected:
                title += " [ПРОБОЙ]"
                if "та же базовая свеча" in breakout_description:
                    title += " (та же база)"
                else:
                    title += " (новая структура)"
            elif need_regular_update:
                title += " [РЕГУЛЯРНОЕ ОБНОВЛЕНИЕ]"
            
            plot_png(candles, current_levels, img_path, title=title)
            
            if not os.path.exists(img_path) or os.path.getsize(img_path) < 1000:
                logging.error("[CHART] Не удалось создать график для %s/%s", symbol, tf)
                return False
                
        except Exception as e:
            logging.error("[CHART] Ошибка построения графика: %s", e)
            return False
        
        # 12. Формируем и отправляем сообщение
        cap = _format_caption(symbol, tf, candles, current_levels, rsi14, emas, ema_analysis, pats, trend_info)
        
        if breakout_description and "ПРОБОЙ" in breakout_description:
            cap = f"🚨 {breakout_description}\n\n{cap}"
        elif need_regular_update:
            cap = f"🔄 Регулярное обновление {symbol} {tf}\n{cap}"
        
        ok = await tg.send_photo(img_path, cap)
        
        if ok:
            _last_state[key] = state
            _last_sent_candle_ts[key] = curr_ts
            _last_price[key] = curr_price
            logging.info("[SENT] Успешно отправлено %s/%s", symbol, tf)
            return True
        else:
            logging.error("[TG] Не удалось отправить сообщение для %s/%s", symbol, tf)
            return False
        
    except Exception as e:
        logging.error("[ERROR] %s/%s: %s", symbol, tf, e)
        import traceback
        logging.error(traceback.format_exc())
        return False

async def main_loop() -> None:
    """Основной цикл бота с цикличностью."""
    global _last_banner_ts
    
    tg = TGQ()
    sess = aiohttp.ClientSession()
    
    logging.info("🚀 Бот запущен в циклическом режиме")
    
    # Статистика
    cycle_count = 0
    total_sent = 0
    
    try:
        while True:
            cycle_count += 1
            sent_this_cycle = 0
            start_time = time.time()
            
            # Выводим информацию о цикле
            current_time = datetime.now().strftime("%H:%M:%S")
            logging.info(f"🌀 Цикл #{cycle_count} начат в {current_time}")
            
            try:
                # Обрабатываем все пары по очереди
                for symbol, tfs in SYMBOLS_TFS.items():
                    for tf in tfs:
                        try:
                            if await run_symbol_tf(sess, tg, symbol, tf):
                                sent_this_cycle += 1
                                total_sent += 1
                            await asyncio.sleep(1)  # Задержка между парами
                        except Exception as e:
                            logging.error(f"[PAIR ERROR] {symbol}/{tf}: {e}")
                
                # Статистика цикла
                cycle_duration = time.time() - start_time
                logging.info(f"🌀 Цикл #{cycle_count} завершен: отправлено {sent_this_cycle} сообщений, длительность {cycle_duration:.2f}с, всего отправлено {total_sent}")
                
                # Отправляем баннер раз в 30 минут если были отправки
                now = time.time()
                if sent_this_cycle > 0 and (now - _last_banner_ts) >= 1800:
                    banner_text = "📊 <b>Market Monitor Active</b>\n"
                    banner_text += f"Обработано пар: {len(SYMBOLS_TFS)}\n"
                    banner_text += f"Отправлено в этом цикле: {sent_this_cycle}\n"
                    banner_text += f"Всего отправлено: {total_sent}"
                    
                    if await tg.send_text(banner_text, kb_main()):
                        _last_banner_ts = now
                        logging.info("[BANNER] Отправлен баннер")
                
                # Пауза перед следующим циклом (основной цикл)
                sleep_time = 10  # 10 секунд между циклами
                logging.info(f"⏳ Ожидание следующего цикла через {sleep_time} секунд...")
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logging.error("[LOOP] Ошибка в основном цикле: %s", e)
                import traceback
                logging.error(traceback.format_exc())
                await asyncio.sleep(30)  # Пауза при ошибке
            
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("🛑 Бот остановлен пользователем")
    finally:
        # Корректное закрытие
        try:
            await sess.close()
            logging.info("Сессия закрыта")
        except Exception:
            pass

def main():
    """Точка входа."""
    try:
        # Очистка старых файлов
        if os.path.exists(OUT_DIR):
            for f in os.listdir(OUT_DIR):
                if f.endswith('.png'):
                    file_path = os.path.join(OUT_DIR, f)
                    file_age = time.time() - os.path.getmtime(file_path)
                    if file_age > 3600:  # Удаляем файлы старше 1 часа
                        os.remove(file_path)
        
        # Запуск основного цикла
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logging.error("Критическая ошибка: %s", e)
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()