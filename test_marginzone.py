#!/usr/bin/env python3
"""
Тестовый скрипт для проверки MarginZoneEngine без запуска всего бота.
"""

import sys
import os
import logging

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)

print("🧪 Тестирование MarginZoneEngine...")

try:
    # 1. Тест импорта модулей
    print("1. Импорт модулей...")
    from margin_zone_engine import MarginZoneEngine, MarginZoneConfig
    print("✅ margin_zone_engine - OK")
    
    from margin_integration import MarginZoneIntegrator
    print("✅ margin_integration - OK")
    
    # 2. Тест создания движка
    print("\n2. Создание движка...")
    config = MarginZoneConfig()
    engine = MarginZoneEngine('BTCUSDT', '5m', config)
    print(f"✅ Движок создан: {engine.symbol} {engine.timeframe}")
    
    # 3. Тест интегратора
    print("\n3. Тест интегратора...")
    integrator = MarginZoneIntegrator()
    integrator.add_symbol('BTCUSDT', '5m')
    print(f"✅ Интегратор создан, движков: {len(integrator.engines)}")
    
    # 4. Проверка БД
    print("\n4. Проверка базы данных...")
    history = integrator.get_event_history()
    print(f"✅ БД доступна, записей: {len(history)}")
    
    # 5. Тест создания таблицы
    print("\n5. Проверка структуры таблицы...")
    import sqlite3
    conn = sqlite3.connect('margin_zones.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(zone_events)")
    columns = cursor.fetchall()
    print(f"✅ Таблица zone_events, колонок: {len(columns)}")
    
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
    
    conn.close()
    
    # 6. Очистка
    integrator.close()
    
    print("\n🎉 Все тесты пройдены успешно!")
    
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)