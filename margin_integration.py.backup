"""
Модуль интеграции MarginZoneEngine с существующим ботом.
Подключает: SQLite, Telegram, основной цикл обработки.
"""

import os
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from margin_zone_engine import MarginZoneEngine, ZoneState, MarginZoneConfig

# Настройка логирования
logger = logging.getLogger(__name__)

class MarginZoneIntegrator:
    """
    Интегратор для управления несколькими движками и подключения внешних систем.
    """
    
    def __init__(self, telegram_client=None, db_path: str = 'margin_zones.db'):
        """
        Инициализация интегратора.
        
        Args:
            telegram_client: клиент Telegram из tg.py (опционально)
            db_path: путь к файлу базы данных SQLite
        """
        # Словарь движков по символам
        self.engines: Dict[str, MarginZoneEngine] = {}
        
        # Клиент Telegram (если передан)
        self.tg_client = telegram_client
        
        # Подключение к SQLite с проверкой создания таблицы
        self.db_path = db_path
        self.db_conn = sqlite3.connect(db_path, check_same_thread=False)
        
        # Гарантированно создаем таблицу при инициализации
        self._init_database()
        
        logger.info(f"MarginZoneIntegrator инициализирован, база данных: {os.path.abspath(db_path)}")
        
    def _init_database(self):
        """Инициализация таблицы в SQLite. Вызывается автоматически при создании."""
        try:
            cursor = self.db_conn.cursor()
            
            # Проверяем, существует ли таблица
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='zone_events'
            """)
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                logger.info("Таблица zone_events не найдена, создаём...")
                
            # Создаем таблицу (если не существует)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS zone_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    event TEXT NOT NULL,
                    upper REAL,
                    lower REAL,
                    center REAL,
                    inside_bars INTEGER,
                    false_breaks INTEGER,
                    zone_id TEXT
                )
            """)
            
            # Создаем индекс (если не существует)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_time 
                ON zone_events (symbol, timestamp DESC)
            """)
            
            self.db_conn.commit()
            
            if not table_exists:
                logger.info("✅ Таблица zone_events успешно создана")
            else:
                logger.info("✅ Таблица zone_events уже существует")
                
            # Проверяем структуру таблицы
            cursor.execute("PRAGMA table_info(zone_events)")
            columns = cursor.fetchall()
            logger.debug(f"Структура таблицы: {len(columns)} колонок")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            raise
        
    def add_symbol(self, symbol: str, timeframe: str, config: Optional[MarginZoneConfig] = None):
        """
        Добавление символа для мониторинга.
        
        Args:
            symbol: торговый символ (BTCUSDT, ETHUSDT, etc)
            timeframe: таймфрейм (5m, 15m, 1h, etc)
            config: конфигурация MarginZoneConfig (опционально)
        """
        engine_key = f"{symbol}_{timeframe}"
        if engine_key not in self.engines:
            self.engines[engine_key] = MarginZoneEngine(
                symbol=symbol,
                timeframe=timeframe,
                config=config
            )
            logger.info(f"Добавлен мониторинг: {symbol} ({timeframe})")
            
    async def process_candles(self, symbol: str, timeframe: str, candles: List[Dict[str, Any]]):
        """
        Основной метод обработки новых свечей.
        Вызывается из основного цикла бота.
        
        Args:
            symbol: торговый символ
            timeframe: таймфрейм
            candles: список свечей в формате словаря
        """
        engine_key = f"{symbol}_{timeframe}"
        if engine_key not in self.engines:
            logger.warning(f"Движок для {symbol} ({timeframe}) не найден")
            return
            
        engine = self.engines[engine_key]
        
        # 1. Обновляем свечи в движке
        engine.update_candles(candles)
        
        # 2. Обрабатываем и получаем событие
        event = engine.process()
        if not event:
            return
            
        # 3. Получаем информацию о зоне
        zone_info = engine.get_zone_info()
        
        # 4. Сохраняем в базу данных
        self._save_event_to_db(symbol, timeframe, event, zone_info)
        
        # 5. Отправляем в Telegram (если подключен)
        await self._send_telegram_notification(symbol, timeframe, event, zone_info)
        
        # 6. Логируем событие
        logger.info(f"📊 {symbol} {timeframe}: {event.name}")
        
    def _save_event_to_db(self, symbol: str, timeframe: str, event: ZoneState, zone_info: Dict[str, Any]):
        """Сохранение события в SQLite."""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("""
                INSERT INTO zone_events 
                (timestamp, symbol, timeframe, event, upper, lower, center, 
                 inside_bars, false_breaks, zone_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(datetime.now().timestamp() * 1000),
                symbol,
                timeframe,
                event.name,
                zone_info.get('upper') if zone_info else None,
                zone_info.get('lower') if zone_info else None,
                zone_info.get('center') if zone_info else None,
                zone_info.get('inside_bars', 0) if zone_info else 0,
                zone_info.get('false_breaks', 0) if zone_info else 0,
                zone_info.get('id') if zone_info else None
            ))
            self.db_conn.commit()
            
            # Логируем успешное сохранение
            logger.debug(f"💾 Сохранено событие в БД: {symbol} {timeframe} - {event.name}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в БД: {e}")
            # При ошибке пытаемся пересоздать таблицу
            try:
                self._init_database()
                logger.info("Повторная попытка сохранения после пересоздания таблицы...")
                self._save_event_to_db(symbol, timeframe, event, zone_info)
            except Exception as e2:
                logger.error(f"❌ Критическая ошибка БД: {e2}")
            
    async def _send_telegram_notification(self, symbol: str, timeframe: str, event: ZoneState, zone_info: Dict[str, Any]):
        """Отправка уведомления в Telegram."""
        if not self.tg_client:
            return
            
        # Форматирование сообщения
        emoji_map = {
            'CREATED': '🆕',
            'ENTERED': '🔵',
            'FALSE_BREAK': '🔄',
            'HOLD': '⏸️',
            'EXIT_IMPULSE': '🚀',
            'EXPIRED': '⏹️'
        }
        
        emoji = emoji_map.get(event.name, '📊')
        
        message = f"""
{emoji} *Margin Zone Event* {emoji}

*Symbol:* {symbol}
*Timeframe:* {timeframe}
*Event:* {event.name}
*Time:* {datetime.now().strftime('%H:%M:%S')}

"""
        
        if zone_info:
            message += f"""
*Zone Range:* {zone_info.get('upper', 0):.4f} - {zone_info.get('lower', 0):.4f}
*Center:* {zone_info.get('center', 0):.4f}
*Inside Bars:* {zone_info.get('inside_bars', 0)}
*False Breaks:* {zone_info.get('false_breaks', 0)}
"""
        
        # Отправка сообщения
        try:
            # Используем асинхронный вызов
            await self.tg_client.send_message(message, parse_mode='Markdown')
            logger.debug(f"📤 Отправлено в Telegram: {symbol} {timeframe} - {event.name}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в Telegram: {e}")
            
    def get_active_zones(self) -> Dict[str, Any]:
        """Получение информации обо всех активных зонах."""
        result = {}
        for key, engine in self.engines.items():
            zone_info = engine.get_zone_info()
            if zone_info:
                result[key] = zone_info
        return result
        
    def get_event_history(self, symbol: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получение истории событий из БД.
        
        Args:
            symbol: фильтр по символу (опционально)
            limit: количество записей
        """
        try:
            cursor = self.db_conn.cursor()
            
            if symbol:
                cursor.execute("""
                    SELECT * FROM zone_events 
                    WHERE symbol = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (symbol, limit))
            else:
                cursor.execute("""
                    SELECT * FROM zone_events 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            result = [dict(zip(columns, row)) for row in rows]
            logger.debug(f"📖 Получено {len(result)} записей из БД")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка чтения из БД: {e}")
            return []
            
    def close(self):
        """Корректное закрытие соединений."""
        try:
            self.db_conn.close()
            logger.info("✅ MarginZoneIntegrator остановлен, соединение с БД закрыто")
        except Exception as e:
            logger.error(f"❌ Ошибка при закрытии БД: {e}")