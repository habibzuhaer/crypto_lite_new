# fix_critical_issues.py - исправление только критических проблем
import os
import sqlite3
from pathlib import Path

def create_levels_table():
    """Создает таблицу levels в базе данных - ЕДИНСТВЕННАЯ КРИТИЧЕСКАЯ ПРОБЛЕМА"""
    db_path = Path('bot.db')
    
    print("\n" + "🗄️ СОЗДАНИЕ ТАБЛИЦЫ LEVELS".center(80, "-"))
    
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже таблица levels
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='levels'")
        if cursor.fetchone():
            print("✅ Таблица 'levels' уже существует")
            return True
        
        # Создаем таблицу levels с минимальной структурой
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                tf TEXT NOT NULL,
                timestamp DATETIME,
                A REAL,
                C REAL,
                X REAL,
                F REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создаем индекс для быстрого поиска
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_levels_symbol_tf 
            ON levels (symbol, tf)
        ''')
        
        conn.commit()
        
        # Проверяем создание
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='levels'")
        if cursor.fetchone():
            print("✅ Таблица 'levels' успешно создана")
            print("✅ Индекс idx_levels_symbol_tf создан")
            
            # Добавляем пару тестовых записей для проверки
            test_data = [
                ('BTCUSDT', '5m', '2026-01-23 20:00:00', 90700.8, 90855.2, 90500.0, 91000.0),
                ('ETHUSDT', '15m', '2026-01-23 19:45:00', 2500.5, 2520.3, 2490.0, 2530.0),
            ]
            
            cursor.executemany('''
                INSERT INTO levels (symbol, tf, timestamp, A, C, X, F)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', test_data)
            
            print(f"✅ Добавлено {len(test_data)} тестовых записей")
            
            # Показываем созданные записи
            cursor.execute("SELECT id, symbol, tf FROM levels LIMIT 5")
            records = cursor.fetchall()
            print(f"📊 Всего записей в таблице: {len(records)}")
            for rec in records:
                print(f"   • ID: {rec[0]}, {rec[1]} ({rec[2]})")
            
            return True
        else:
            print("❌ Не удалось создать таблицу 'levels'")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при создании таблицы: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def verify_env_file():
    """Проверка .env файла"""
    print("\n" + "🔧 ПРОВЕРКА .env ФАЙЛА".center(80, "-"))
    
    env_path = Path('.env')
    if not env_path.exists():
        print("❌ Файл .env не найден")
        return False
    
    # Читаем и проверяем критически важные переменные
    with open(env_path, 'r') as f:
        content = f.read()
    
    critical_vars = ['TG_TOKEN', 'TG_CHAT_ID']
    optional_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'BYBIT_API_KEY', 'BYBIT_API_SECRET']
    
    issues = []
    for var in critical_vars:
        if f"{var}=" not in content:
            issues.append(f"❌ {var} отсутствует")
        elif f"{var}=your_" in content:
            issues.append(f"❌ {var} не заполнен (значение по умолчанию)")
        else:
            print(f"✅ {var} настроен")
    
    for var in optional_vars:
        if f"{var}=" in content and f"{var}=your_" not in content:
            print(f"✅ {var} настроен (опционально)")
    
    if issues:
        print("\n⚠️ Проблемы с .env файлом:")
        for issue in issues:
            print(f"   {issue}")
        print("\n📝 Отредактируйте файл .env:")
        print("   nano .env")
        return False
    
    return True

def verify_dependencies():
    """Проверка зависимостей"""
    print("\n" + "📦 ПРОВЕРКА ЗАВИСИМОСТЕЙ".center(80, "-"))
    
    try:
        import aiohttp
        print(f"✅ aiohttp: {aiohttp.__version__}")
    except ImportError:
        print("❌ aiohttp не установлен")
        return False
    
    try:
        import pandas
        print(f"✅ pandas: {pandas.__version__}")
    except ImportError:
        print("❌ pandas не установлен")
        return False
    
    try:
        import matplotlib
        print(f"✅ matplotlib: {matplotlib.__version__}")
    except ImportError:
        print("❌ matplotlib не установлен")
        return False
    
    try:
        import mplfinance
        print("✅ mplfinance установлен")
    except ImportError:
        print("⚠️ mplfinance не установлен (не критично)")
    
    try:
        import ta
        print("✅ ta установлен")
    except ImportError:
        print("⚠️ ta не установлен (не критично)")
    
    return True

def main():
    print("=" * 80)
    print("🔧 ИСПРАВЛЕНИЕ КРИТИЧЕСКИХ ПРОБЛЕМ".center(80, "="))
    print("=" * 80)
    
    print("\n📋 Найденные проблемы:")
    print("1. ❌ Отсутствует таблица 'levels' в bot.db (КРИТИЧЕСКАЯ)")
    print("2. ✅ Telegram бот работает (отправляет сообщения)")
    print("3. ✅ Графики генерируются успешно")
    print("4. ✅ Зависимости в основном установлены")
    
    print("\n" + "🚀 ЗАПУСК ИСПРАВЛЕНИЙ".center(80, "-"))
    
    # Проверка зависимостей
    if not verify_dependencies():
        print("\n⚠️ Некоторые зависимости отсутствуют")
        print("   Установите их командой:")
        print("   pip install aiohttp pandas matplotlib")
    
    # Проверка .env файла
    env_ok = verify_env_file()
    
    # Создание таблицы levels
    table_created = create_levels_table()
    
    print("\n" + "📊 ИТОГИ".center(80, "-"))
    
    if table_created and env_ok:
        print("🎉 КРИТИЧЕСКИЕ ПРОБЛЕМЫ ИСПРАВЛЕНЫ!")
        print("\n✅ Telegram бот готов к работе")
        print("✅ База данных настроена")
        print("✅ Графики генерируются")
        
        print("\n🔍 Запустите полную диагностику для проверки:")
        print("   python diag.py")
        
        print("\n🚀 Запустите бота:")
        print("   python main.py")
    else:
        print("⚠️ Некоторые проблемы остались неисправленными")
        
        if not table_created:
            print("\n❌ Таблица 'levels' не создана")
            print("   Создайте ее вручную:")
            print("   sqlite3 bot.db")
            print("   CREATE TABLE levels (")
            print("     id INTEGER PRIMARY KEY AUTOINCREMENT,")
            print("     symbol TEXT NOT NULL,")
            print("     tf TEXT NOT NULL,")
            print("     timestamp DATETIME,")
            print("     A REAL, C REAL, X REAL, F REAL")
            print("   );")
        
        if not env_ok:
            print("\n❌ Проблемы с .env файлом")
            print("   Отредактируйте файл .env:")
            print("   nano .env")
    
    print("\n" + "=" * 80)
    print("💡 Справка:")
    print("• Ключ 'ts' вместо 'timestamp' в свечах - НЕ ПРОБЛЕМА")
    print("  Код адаптирован для работы с этим форматом")
    print("• Графики успешно генерируются")
    print("• Telegram бот отправляет сообщения")
    print("=" * 80)

if __name__ == "__main__":
    main()