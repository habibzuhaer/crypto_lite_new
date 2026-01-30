"""
ПРИМЕР встраивания MarginZoneEngine в твоего бота.
Замени 'your_candle_source' и 'your_telegram_module'.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any
from margin_zone_engine import MarginZoneEngine, ZoneState

class BotWithMarginZones:
    def __init__(self):
        # 1. Инициализация engine для каждого символа
        self.engines: Dict[str, MarginZoneEngine] = {
            'BTCUSDT': MarginZoneEngine('BTCUSDT', '5m'),
            'ETHUSDT': MarginZoneEngine('ETHUSDT', '5m')
        }
        
        # 2. Подключение БД (если нет — создастся)
        self.db_conn = sqlite3.connect('margin_zones.db', check_same_thread=False)
        self._init_db()
        
        # 3. Твой существующий модуль Telegram (из tg.py)
        self.tg_client = None  # Импортируй свой
        
    def _init_db(self):
        """Таблица для событий. Вызывается once."""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS zone_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                symbol TEXT,
                event TEXT,
                upper REAL,
                lower REAL,
                details TEXT
            )
        """)
        self.db_conn.commit()
        
    def on_new_candles(self, symbol: str, candles: List[Dict[str, Any]]):
        """
        Вызывай из основного цикла бота при получении новых свечей.
        candles: твой текущий формат (список dict).
        """
        engine = self.engines.get(symbol)
        if not engine:
            return
            
        # 1. Обновляем движок свечами
        engine.update_candles(candles)
        
        # 2. Обрабатываем -> получаем событие
        event = engine.process()
        if not event:
            return
            
        # 3. Действия по событию
        zone_info = engine.get_zone_info()
        
        # 3.1 Сохранить в SQLite
        self._save_to_db(symbol, event, zone_info)
        
        # 3.2 Уведомить в Telegram
        self._send_to_telegram(symbol, event, zone_info)
        
        # 3.3 (Опционально) Твой торговый логик
        self._on_zone_event(symbol, event, zone_info)
        
    def _save_to_db(self, symbol: str, event: ZoneState, zone_info: Dict[str, Any]):
        """Логирование события в SQLite."""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            INSERT INTO zone_events 
            (timestamp, symbol, event, upper, lower, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            int(datetime.now().timestamp() * 1000),
            symbol,
            event.name,
            zone_info.get('upper') if zone_info else None,
            zone_info.get('lower') if zone_info else None,
            str(zone_info) if zone_info else ''
        ))
        self.db_conn.commit()
        
    def _send_to_telegram(self, symbol: str, event: ZoneState, zone_info: Dict[str, Any]):
        """
        Отправка уведомления. Использует твой исправленный tg.py.
        """
        if not self.tg_client:
            return
            
        # Форматируем сообщение
        msg = f"""
[{symbol}] Margin Zone Event
State: {event.name}
Zone: {zone_info.get('upper', 0):.2f} - {zone_info.get('lower', 0):.2f}
Inside bars: {zone_info.get('inside_bars', 0)}
False breaks: {zone_info.get('false_breaks', 0)}
        """.strip()
        
        # Отправляем (асинхронно, если нужно)
        # await self.tg_client.send_message(msg)
        
    def _on_zone_event(self, symbol: str, event: ZoneState, zone_info: Dict[str, Any]):
        """
        Сюда добавь свою логику (например, при EXIT_IMPULSE — ждать отката).
        Engine НЕ торгует, только информирует.
        """
        if event == ZoneState.FALSE_BREAK:
            self.logger.info(f"[{symbol}] Ложный выход! Маржинальный стоп-ран.")
        elif event == ZoneState.EXIT_IMPULSE:
            self.logger.info(f"[{symbol}] Импульсный выход. Можно искать вход.")