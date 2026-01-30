#!/usr/bin/env python3
"""
Скрипт для проверки и создания базы данных MarginZone.
Запустите этот скрипт перед первым запуском бота.
"""

import os
import sqlite3
import sys

def check_and_create_db(db_path='margin_zones.db'):
    """Проверяет и создает базу данных при необходимости."""
    
    print(f"🔍 Проверяем базу данных: {os.path.abspath(db_path)}")
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем существование таблицы
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='zone_events'
        """)
        
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            print("📦 Таблица zone_events не найдена, создаём...")
            
            # Создаем таблицу
            cursor.execute("""
                CREATE TABLE zone_events (
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
            
            # Создаем индекс
            cursor.execute("""
                CREATE INDEX idx_symbol_time 
                ON zone_events (symbol, timestamp DESC)
            """)
            
            conn.commit()
            print("✅ Таблица zone_events успешно создана")
        else:
            print("✅ Таблица zone_events уже существует")
        
        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(zone_events)")
        columns = cursor.fetchall()
        
        print(f"\n📊 Структура таблицы zone_events ({len(columns)} колонок):")
        print("-" * 60)
        print(f"{'ID':<3} {'Название':<15} {'Тип':<12} {'Nullable':<8}")
        print("-" * 60)
        for col in columns:
            print(f"{col[0]:<3} {col[1]:<15} {col[2]:<12} {'NO' if col[3] else 'YES':<8}")
        
        # Проверяем, есть ли данные
        cursor.execute("SELECT COUNT(*) FROM zone_events")
        count = cursor.fetchone()[0]
        print(f"\n📈 Количество записей в таблице: {count}")
        
        if count > 0:
            print("\n📋 Последние 5 записей:")
            cursor.execute("""
                SELECT timestamp, symbol, timeframe, event 
                FROM zone_events 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            
            from datetime import datetime
            for row in cursor.fetchall():
                ts = datetime.fromtimestamp(row[0] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                print(f"  {ts} | {row[1]:<10} | {row[2]:<5} | {row[3]}")
        
        conn.close()
        print(f"\n🎉 База данных готова к использованию!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_and_create_db()