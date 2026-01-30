# -*- coding: utf-8 -*-
# diag.py — полная диагностика проекта: среды, зависимостей, БД, импортов и функционала

import os
import sys
import ast
import inspect
import sqlite3
import asyncio
import aiohttp
import traceback
import importlib
import platform
import json
from datetime import datetime
from typing import Dict, List, Tuple, Any
from dotenv import load_dotenv
from pathlib import Path

print("=" * 80)
print("🚀 ПОЛНАЯ ДИАГНОСТИКА ПРОЕКТА")
print(f"📅 Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# -------------------- БАЗОВАЯ ИНФОРМАЦИЯ О СИСТЕМЕ --------------------
def check_system_info():
    print("\n" + "🔍 ИНФОРМАЦИЯ О СИСТЕМЕ".center(80, "-"))
    print(f"• Python: {platform.python_version()} ({platform.python_implementation()})")
    print(f"• Система: {platform.system()} {platform.release()}")
    print(f"• Процессор: {platform.processor()}")
    print(f"• Рабочий каталог: {os.getcwd()}")
    print(f"• Файл скрипта: {__file__}")

check_system_info()

# -------------------- ПРОВЕРКА И НАСТРОЙКА .env ФАЙЛА --------------------
def setup_env_file():
    print("\n" + "🔧 НАСТРОЙКА .env ФАЙЛА".center(80, "-"))
    
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ Файл .env не найден! Создаю шаблон...")
        template = """# Telegram Bot (старые имена для совместимости)
TG_TOKEN=your_telegram_bot_token_here
TG_CHAT_ID=your_telegram_chat_id_here

# Telegram Bot (новые имена)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Bybit API (опционально)
BYBIT_API_KEY=your_bybit_api_key_here
BYBIT_API_SECRET=your_bybit_api_secret_here

# Database
DATABASE_URL=sqlite:///bot.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=bot.log
"""
        env_file.write_text(template)
        print("✅ Создан шаблон .env файла")
        print("⚠️ Пожалуйста, заполните TG_TOKEN/TELEGRAM_BOT_TOKEN и TG_CHAT_ID/TELEGRAM_CHAT_ID")
    else:
        print(f"✅ Файл .env найден ({env_file.stat().st_size} байт)")
        
        # Читаем и проверяем содержимое
        content = env_file.read_text()
        lines = content.strip().split('\n')
        
        # Проверяем наличие всех необходимых переменных
        required_vars = ['TG_TOKEN', 'TG_CHAT_ID', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
        found_vars = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key = line.split('=', 1)[0].strip()
                    found_vars.append(key)
        
        for var in required_vars:
            if var not in found_vars:
                print(f"⚠️ Переменная {var} не найдена в .env файле")

setup_env_file()

# Загружаем .env после возможного создания
load_dotenv()

print("\n" + "🔧 ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ".center(80, "-"))

# Проверяем все возможные варианты имен переменных
env_configs = [
    {
        'token_name': 'TG_TOKEN',
        'chat_name': 'TG_CHAT_ID',
        'description': 'Telegram Bot (старые имена)'
    },
    {
        'token_name': 'TELEGRAM_BOT_TOKEN', 
        'chat_name': 'TELEGRAM_CHAT_ID',
        'description': 'Telegram Bot (новые имена)'
    }
]

working_config = None

for config in env_configs:
    token = os.getenv(config['token_name'], '')
    chat_id = os.getenv(config['chat_name'], '')
    
    if token and token != 'your_telegram_bot_token_here' and chat_id and chat_id != 'your_telegram_chat_id_here':
        working_config = config
        print(f"✅ Используется конфигурация: {config['description']}")
        print(f"   • {config['token_name']}: {token[:10]}...{token[-5:] if len(token) > 15 else ''}")
        print(f"   • {config['chat_name']}: {chat_id}")
        break

if not working_config:
    print("❌ Не найдена рабочая конфигурация Telegram бота!")
    print("   Проверьте .env файл и убедитесь, что установлены:")
    print("   - TG_TOKEN и TG_CHAT_ID ИЛИ")
    print("   - TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID")

# Другие переменные окружения
other_vars = [
    ('BYBIT_API_KEY', False, 'API ключ Bybit'),
    ('BYBIT_API_SECRET', False, 'Секрет Bybit'),
    ('DATABASE_URL', False, 'URL базы данных'),
]

print("\n📋 Другие переменные окружения:")
for var_name, required, description in other_vars:
    value = os.getenv(var_name, '')
    status = "✅" if value else "⚠️" if not required else "❌"
    masked = f"{len(value)} символов" if value and (var_name.endswith('_KEY') or var_name.endswith('_SECRET')) else value
    req_mark = "[ОБЯЗАТЕЛЬНО]" if required else "[ОПЦИОНАЛЬНО]"
    print(f"{status} {var_name}: {masked} {req_mark} — {description}")

# -------------------- УСТАНОВКА ОТСУТСТВУЮЩИХ ЗАВИСИМОСТЕЙ --------------------
def check_and_install_dependencies():
    print("\n" + "📦 ПРОВЕРКА И УСТАНОВКА ЗАВИСИМОСТЕЙ".center(80, "-"))
    
    dependencies = [
        ('ta', 'TA-Lib для технического анализа'),
        ('mplfinance', 'Библиотека для финансовых графиков'),
    ]
    
    missing_deps = []
    
    for pip_name, description in dependencies:
        try:
            importlib.import_module(pip_name)
            print(f"✅ {pip_name}: установлен ({description})")
        except ImportError:
            print(f"❌ {pip_name}: НЕ УСТАНОВЛЕН ({description})")
            missing_deps.append(pip_name)
    
    if missing_deps:
        print(f"\n⚠️ Отсутствуют зависимости: {', '.join(missing_deps)}")
        print("Вы можете установить их командой:")
        print(f"  pip install {' '.join(missing_deps)}")
        
        # Спросить пользователя
        try:
            response = input("\nУстановить отсутствующие зависимости сейчас? (y/N): ").strip().lower()
            if response == 'y':
                print("Установка зависимостей...")
                import subprocess
                for dep in missing_deps:
                    try:
                        subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
                        print(f"✅ {dep} установлен")
                    except subprocess.CalledProcessError:
                        print(f"❌ Ошибка при установке {dep}")
        except (KeyboardInterrupt, EOFError):
            print("\nУстановка отменена пользователем")
    
    # Дополнительные проверки
    print("\n📋 Основные зависимости:")
    try:
        import aiohttp
        print(f"✅ aiohttp: {aiohttp.__version__}")
    except ImportError:
        print("❌ aiohttp: не установлен")
        
    try:
        import pandas
        print(f"✅ pandas: {pandas.__version__}")
    except ImportError:
        print("❌ pandas: не установлен")
        
    try:
        import matplotlib
        print(f"✅ matplotlib: {matplotlib.__version__}")
    except ImportError:
        print("❌ matplotlib: не установлен")

check_and_install_dependencies()

# -------------------- СТРУКТУРА ПРОЕКТА --------------------
def scan_project_structure():
    print("\n" + "📁 СТРУКТУРА ПРОЕКТА".center(80, "-"))
    
    project_root = Path(__file__).parent
    print(f"Корень проекта: {project_root}")
    
    # Игнорируемые директории
    ignored_dirs = ['venv', '__pycache__', '.git', '.idea', '.vscode', 'copy', 'copyorigin']
    
    # Считаем файлы по типам
    file_types = {
        '.py': 'Python файлы',
        '.db': 'Базы данных',
        '.png': 'Графики',
        '.json': 'JSON файлы',
        '.txt': 'Текстовые файлы',
        '.md': 'Документация',
    }
    
    counts = {ext: 0 for ext in file_types.keys()}
    total_size = 0
    python_files = []
    
    for file_path in project_root.rglob('*'):
        # Пропускаем игнорируемые директории
        if any(ignored in str(file_path) for ignored in ignored_dirs):
            continue
            
        if file_path.is_file():
            total_size += file_path.stat().st_size
            ext = file_path.suffix.lower()
            if ext in counts:
                counts[ext] += 1
            if ext == '.py':
                python_files.append(file_path)
    
    print("\n📊 Статистика файлов (без игнорируемых директорий):")
    for ext, description in file_types.items():
        count = counts[ext]
        if count > 0:
            print(f"  {description}: {count} файлов")
    
    print(f"\n📊 Общий размер проекта: {total_size / 1024 / 1024:.2f} MB")
    print(f"🐍 Python файлов: {len(python_files)}")
    
    # Выводим структуру основных директорий
    print("\n📂 Основные директории проекта:")
    for item in sorted(project_root.iterdir()):
        if item.is_dir() and not item.name.startswith('.') and item.name not in ignored_dirs:
            py_count = len(list(item.rglob('*.py')))
            if py_count > 0 or any(item.name.startswith(prefix) for prefix in ['out', 'data', 'logs']):
                size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file()) / 1024
                print(f"  • {item.name}/ ({py_count} .py файлов, {size:.1f} KB)")

scan_project_structure()

# -------------------- ПРОВЕРКА БАЗЫ ДАННЫХ --------------------
def check_database():
    print("\n" + "🗄️ БАЗА ДАННЫХ".center(80, "-"))
    
    db_files = list(Path('.').glob('*.db')) + list(Path('.').glob('*.sqlite'))
    
    if not db_files:
        print("❌ Файлы БД не найдены")
        return
    
    for db_file in db_files:
        print(f"\n📊 Анализ БД: {db_file.name} ({db_file.stat().st_size / 1024:.1f} KB)")
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Получаем все таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            print(f"  Таблиц: {len(tables)}")
            
            # Проверяем наличие таблицы levels в bot.db
            if db_file.name == 'bot.db' and not any('levels' in table[0] for table in tables):
                print("  ❌ КРИТИЧЕСКО: Таблица 'levels' отсутствует в bot.db!")
                print("  ⚠️  Эта таблица необходима для работы бота")
                print("  💡 Создать таблицу можно скриптом из проекта")
            
            for table_name, in tables:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                
                print(f"  └─ {table_name}: {row_count} записей, {len(columns)} колонок")
                
                # Для таблицы levels покажем структуру подробнее
                if table_name == 'levels':
                    print("      Колонки:", ", ".join([col[1] for col in columns]))
                    
                    # Проверка на наличие необходимых колонок
                    required_columns = ['symbol', 'tf', 'A', 'C', 'timestamp']
                    existing_columns = [col[1] for col in columns]
                    missing = [col for col in required_columns if col not in existing_columns]
                    if missing:
                        print(f"      ❌ Отсутствуют колонки: {', '.join(missing)}")
                    else:
                        print(f"      ✅ Все необходимые колонки присутствуют")
                    
                    # Пример данных
                    cursor.execute("SELECT symbol, tf, COUNT(*) FROM levels GROUP BY symbol, tf ORDER BY COUNT(*) DESC LIMIT 3")
                    top_pairs = cursor.fetchall()
                    if top_pairs:
                        print("      Топ пар по количеству уровней:")
                        for symbol, tf, count in top_pairs:
                            print(f"        {symbol} ({tf}): {count} уровней")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Ошибка при анализе БД {db_file}: {e}")

check_database()

# -------------------- ПРОВЕРКА ИМПОРТОВ ПРОЕКТА --------------------
def check_imports():
    print("\n" + "🔄 ИМПОРТЫ ПРОЕКТА".center(80, "-"))
    
    modules_to_check = [
        ('futures_bybit', 'fb'),
        ('strategy_levels', 'st'),
        ('charting', 'ch'),
        ('tg', 'tg'),
        ('main', 'main'),
    ]
    
    for module_name, alias in modules_to_check:
        try:
            module = importlib.import_module(module_name)
            print(f"✅ {module_name}: импортирован успешно")
            
            # Получаем все функции модуля
            functions = [name for name in dir(module) if not name.startswith('_') and callable(getattr(module, name))]
            
            if module_name == 'futures_bybit':
                print(f"    Доступные функции: {', '.join(functions[:5])}" + (f"... (всего {len(functions)})" if len(functions) > 5 else ""))
                # Проверяем ключевые функции
                for func in ['fetch_kline', 'get_current_price']:
                    if hasattr(module, func):
                        print(f"    └─ ✅ {func}() доступна")
                    else:
                        print(f"    └─ ❌ {func}() не найдена")
                        
            elif module_name == 'tg':
                print(f"    Доступные функции: {', '.join(functions[:10])}" + (f"... (всего {len(functions)})" if len(functions) > 10 else ""))
                
                # Ищем класс TelegramBot
                telegram_class = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and 'Telegram' in attr_name and 'Bot' in attr_name:
                        telegram_class = attr
                        print(f"    └─ ✅ Найден класс: {attr_name}")
                        break
                
                if telegram_class:
                    # Показываем методы класса
                    methods = [name for name in dir(telegram_class) if not name.startswith('_') and callable(getattr(telegram_class, name))]
                    if methods:
                        print(f"        Методы класса: {', '.join(methods[:5])}" + (f"... (всего {len(methods)})" if len(methods) > 5 else ""))
                
            elif module_name in ['strategy_levels', 'charting']:
                key_funcs = {
                    'strategy_levels': ['calculate_levels', 'pick_biggest_candle', 'calculate_rsi'],
                    'charting': ['plot_png']
                }
                for func in key_funcs.get(module_name, []):
                    if hasattr(module, func):
                        print(f"    └─ ✅ {func}() доступна")
                    else:
                        print(f"    └─ ❌ {func}() не найдена")
            
        except ImportError as e:
            print(f"❌ {module_name}: Ошибка импорта - {e}")
        except Exception as e:
            print(f"⚠️ {module_name}: Ошибка при проверке - {e}")

check_imports()

# -------------------- ПРОВЕРКА СИГНАТУР ФУНКЦИЙ --------------------
def check_function_signatures():
    print("\n" + "📝 СИГНАТУРЫ ФУНКЦИЙ".center(80, "-"))
    
    try:
        import strategy_levels as st
        import futures_bybit as fb
        
        functions = [
            ('calculate_levels', st.calculate_levels),
            ('pick_biggest_candle', st.pick_biggest_candle),
            ('calculate_rsi', st.calculate_rsi),
            ('fetch_kline', fb.fetch_kline if hasattr(fb, 'fetch_kline') else None),
        ]
        
        for name, func in functions:
            if func is None:
                print(f"❌ {name}: функция не найдена")
                continue
                
            try:
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                print(f"✅ {name}({', '.join(params)})")
                
                # Проверка параметра use_biggest_from_last
                if name == 'calculate_levels' and 'use_biggest_from_last' in params:
                    print(f"    ⚠️ Используется параметр use_biggest_from_last")
                    # Показываем значение по умолчанию
                    default_value = sig.parameters['use_biggest_from_last'].default
                    print(f"    Значение по умолчанию: {default_value}")
                    
            except Exception as e:
                print(f"❌ {name}: не удалось получить сигнатуру - {e}")
                
    except Exception as e:
        print(f"❌ Ошибка при проверке сигнатур: {e}")

check_function_signatures()

# -------------------- АНАЛИЗ ПРОБЛЕМЫ С TIMESTAMP --------------------
def analyze_timestamp_issue():
    print("\n" + "🔍 АНАЛИЗ ПРОБЛЕМЫ С TIMESTAMP".center(80, "-"))
    
    try:
        import futures_bybit as fb
        
        print("Проверяем структуру данных из fetch_kline...")
        
        async def test_fetch():
            try:
                async with aiohttp.ClientSession() as s:
                    # Пробуем получить данные для одной пары
                    candles = await fb.fetch_kline(s, "BTCUSDT", "5m", 10)
                    
                    if candles and len(candles) > 0:
                        print(f"✅ Получено {len(candles)} свечей")
                        print(f"📊 Структура первой свечи:")
                        
                        first_candle = candles[0]
                        if isinstance(first_candle, dict):
                            for key, value in list(first_candle.items())[:10]:  # Первые 10 ключей
                                print(f"  {key}: {type(value).__name__} = {value}")
                            
                            # Проверяем наличие timestamp или time
                            if 'timestamp' in first_candle:
                                print(f"✅ Ключ 'timestamp' найден")
                            elif 'time' in first_candle:
                                print(f"✅ Ключ 'time' найден (используйте его вместо timestamp)")
                            elif 't' in first_candle:
                                print(f"✅ Ключ 't' найден (используйте его вместо timestamp)")
                            else:
                                print(f"❌ Ключ timestamp/time/t не найден")
                                print(f"   Все ключи: {list(first_candle.keys())}")
                        else:
                            print(f"❌ Свеча не является словарем: {type(first_candle)}")
                    else:
                        print("❌ Не удалось получить свечи")
                        
            except Exception as e:
                print(f"❌ Ошибка при тестировании fetch_kline: {e}")
                traceback.print_exc()
        
        # Запускаем асинхронный тест
        asyncio.run(test_fetch())
        
    except Exception as e:
        print(f"❌ Ошибка при анализе проблемы: {e}")

analyze_timestamp_issue()

# -------------------- ПРОВЕРКА ГЕНЕРАЦИИ ГРАФИКОВ --------------------
OUT_DIR = "out_diag_png"
os.makedirs(OUT_DIR, exist_ok=True)

# Тестовые пары
PAIRS = [
    ("GRTUSDT", "5m"),
    ("ADAUSDT", "15m"),
    ("INJUSDT", "15m"),
    ("LINKUSDT", "4h"),
]

NEED = ["X", "F", "f1", "A", "a1", "C", "c1", "D", "Y"]

async def scan_pair_fixed(symbol: str, tf: str):
    """Исправленная версия scan_pair"""
    tag = f"[{symbol} {tf}]"
    try:
        import futures_bybit as fb
        import strategy_levels as st
        import charting as ch
        
        async with aiohttp.ClientSession() as s:
            print(f"{tag} Запрашиваем свечи...")
            candles = await fb.fetch_kline(s, symbol, tf, 250)
            
            if not candles:
                print(f"{tag} ❌ Нет свечей")
                return None
            
            print(f"{tag} Свечей: {len(candles)}")
            
            # Анализируем структуру данных
            if candles and len(candles) > 0:
                first_candle = candles[0]
                print(f"{tag} Тип свечи: {type(first_candle)}")
                if isinstance(first_candle, dict):
                    # Ищем ключ с временной меткой
                    time_key = None
                    for key in ['timestamp', 'time', 't', 'Timestamp', 'Time']:
                        if key in first_candle:
                            time_key = key
                            break
                    
                    if time_key:
                        print(f"{tag} Используем ключ '{time_key}' для времени")
                    else:
                        print(f"{tag} ⚠️ Временной ключ не найден, доступные ключи: {list(first_candle.keys())}")
            
            # Вычисляем уровни (пробуем с параметром и без)
            try:
                levels = st.calculate_levels(candles, symbol, tf, use_biggest_from_last=180)
            except TypeError:
                # Пробуем без параметра use_biggest_from_last
                print(f"{tag} Пробуем без use_biggest_from_last...")
                levels = st.calculate_levels(candles, symbol, tf)
            
            if not levels:
                print(f"{tag} ❌ Не удалось расчитать уровни")
                return None

            miss = [k for k in NEED if k not in levels]
            if miss:
                print(f"{tag} ⚠️ Отсутствуют ключи: {miss}")
                print(f"{tag} Доступные ключи: {sorted(levels.keys())}")
                # Продолжаем, даже если не все ключи есть

            # Выводим основные уровни
            level_info = []
            for key in ['A', 'C', 'X', 'F']:
                if key in levels:
                    level_info.append(f"{key}={levels[key]:.6f}")
            
            print(f"{tag} Уровни: {', '.join(level_info)}")

            # Генерируем график
            out = os.path.join(OUT_DIR, f"{symbol}_{tf}.png")
            try:
                ch.plot_png(candles, levels, out, title=f"{symbol} {tf}")
                size = os.path.getsize(out) if os.path.exists(out) else 0
                print(f"{tag} ✅ PNG сохранен: {out} ({size/1024:.1f} KB)")
                return out
            except Exception as e:
                print(f"{tag} ❌ Ошибка plot_png: {type(e).__name__}: {e}")
                traceback.print_exc()
                return None

    except Exception as e:
        print(f"{tag} ❌ {type(e).__name__}: {e}")
        traceback.print_exc()
        return None

async def check_charting_fixed():
    print("\n" + "📈 ТЕСТИРОВАНИЕ ГЕНЕРАЦИИ ГРАФИКОВ".center(80, "-"))
    
    try:
        print(f"Тестирование {len(PAIRS)} пар...")
        
        results = []
        for s, tf in PAIRS:
            result = await scan_pair_fixed(s, tf)
            results.append((s, tf, result is not None))
        
        success = sum(1 for _, _, success in results if success)
        print(f"\n📊 Результаты тестирования графиков: {success}/{len(PAIRS)} успешно")
        
        # Показываем сгенерированные файлы
        png_files = list(Path(OUT_DIR).glob('*.png'))
        if png_files:
            print(f"\n📁 Сгенерированные графики в {OUT_DIR}/:")
            for png in sorted(png_files, key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
                size = png.stat().st_size / 1024
                age = datetime.fromtimestamp(png.stat().st_mtime)
                print(f"  └─ {png.name} ({size:.1f} KB, {age.strftime('%H:%M:%S')})")
        
        return success > 0
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании графиков: {e}")
        traceback.print_exc()
        return False

# -------------------- ПРОВЕРКА TELEGRAM --------------------
async def check_telegram():
    print("\n" + "🤖 ПРОВЕРКА TELEGRAM БОТА".center(80, "-"))
    
    try:
        import tg
        
        # Проверяем обе версии переменных
        token = os.getenv('TG_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TG_CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID')
        
        if not token or token in ['your_telegram_bot_token_here', 'your_bot_token_here']:
            print("❌ Токен Telegram бота не установлен или имеет значение по умолчанию")
            print("   Отредактируйте файл .env и установите реальный токен")
            return False
        
        if not chat_id or chat_id in ['your_telegram_chat_id_here', 'your_chat_id_here']:
            print("❌ Chat ID Telegram не установлен или имеет значение по умолчанию")
            print("   Отредактируйте файл .env и установите реальный chat ID")
            return False
        
        print(f"✅ Токен найден: {token[:10]}...{token[-5:] if len(token) > 15 else ''}")
        print(f"✅ Chat ID: {chat_id}")
        
        # Ищем класс TelegramBot
        telegram_class = None
        for attr_name in dir(tg):
            attr = getattr(tg, attr_name)
            if isinstance(attr, type) and 'Telegram' in attr_name and 'Bot' in attr_name:
                telegram_class = attr
                print(f"✅ Найден класс TelegramBot: {attr_name}")
                break
        
        if telegram_class:
            try:
                # Пытаемся создать экземпляр бота
                print("Пробуем создать экземпляр Telegram бота...")
                bot = telegram_class(token, chat_id)
                print("✅ Экземпляр Telegram бота создан успешно")
                
                # Проверяем методы бота
                methods = [name for name in dir(bot) if not name.startswith('_') and callable(getattr(bot, name))]
                send_methods = [m for m in methods if 'send' in m.lower()]
                
                if send_methods:
                    print(f"✅ Методы отправки: {', '.join(send_methods)}")
                    
                    # Тест отправки сообщения
                    test_msg = f"✅ Тест бота {datetime.now().strftime('%H:%M:%S')}"
                    print(f"Отправка тестового сообщения...")
                    
                    # Ищем метод send_message или аналогичный
                    send_func = None
                    for method_name in ['send_message', 'send', 'notify']:
                        if hasattr(bot, method_name):
                            send_func = getattr(bot, method_name)
                            break
                    
                    if send_func:
                        if asyncio.iscoroutinefunction(send_func):
                            success = await send_func(test_msg)
                        else:
                            success = send_func(test_msg)
                        
                        if success:
                            print("✅ Тестовое сообщение отправлено успешно")
                        else:
                            print("⚠️ Сообщение отправлено, но возвращен False")
                        return True
                    else:
                        print("❌ Не найден метод отправки сообщений")
                else:
                    print("❌ Не найдены методы отправки в классе TelegramBot")
                    
            except Exception as e:
                print(f"⚠️ Ошибка при работе с Telegram ботом: {e}")
                return False
        else:
            print("❌ Не найден класс TelegramBot в модуле tg")
            return False
            
    except ImportError as e:
        print(f"❌ Ошибка импорта модуля tg: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при проверке Telegram: {e}")
        return False

# -------------------- ОБЩАЯ ДИАГНОСТИКА --------------------
def overall_health_check():
    print("\n" + "🏥 ОБЩАЯ ДИАГНОСТИКА".center(80, "-"))
    
    checks = []
    issues = []
    
    # 1. Проверка переменных окружения Telegram
    token = os.getenv('TG_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TG_CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID')
    env_ok = bool(token and token not in ['your_telegram_bot_token_here', 'your_bot_token_here'] and 
                  chat_id and chat_id not in ['your_telegram_chat_id_here', 'your_chat_id_here'])
    checks.append(('Переменные окружения Telegram', env_ok))
    if not env_ok:
        issues.append("• Заполните TG_TOKEN/TELEGRAM_BOT_TOKEN и TG_CHAT_ID/TELEGRAM_CHAT_ID в файле .env")
    
    # 2. Проверка БД
    db_exists = os.path.exists('bot.db')
    checks.append(('База данных bot.db', db_exists))
    if db_exists:
        try:
            conn = sqlite3.connect('bot.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='levels'")
            has_levels = cursor.fetchone() is not None
            conn.close()
            checks.append(('Таблица levels в БД', has_levels))
            if not has_levels:
                issues.append("• В bot.db отсутствует таблица 'levels' (создайте её)")
        except:
            checks.append(('Таблица levels в БД', False))
            issues.append("• Не удалось проверить таблицу levels в БД")
    
    # 3. Проверка ключевых модулей
    try:
        import futures_bybit
        import strategy_levels
        import charting
        import tg
        modules_ok = True
    except Exception as e:
        modules_ok = False
        issues.append(f"• Некоторые модули не импортируются: {e}")
    checks.append(('Ключевые модули', modules_ok))
    
    # 4. Проверка директорий
    out_dir_exists = os.path.exists(OUT_DIR)
    checks.append(('Директория для графиков', out_dir_exists))
    
    # 5. Проверка зависимостей
    try:
        import ta
        import mplfinance
        deps_ok = True
    except:
        deps_ok = False
        issues.append("• Установите зависимости: pip install ta mplfinance")
    checks.append(('Зависимости (ta, mplfinance)', deps_ok))
    
    # Вывод результатов
    passed = sum(1 for _, status in checks if status)
    total = len(checks)
    
    print(f"📊 Пройдено: {passed}/{total} проверок")
    print("-" * 40)
    
    for check_name, status in checks:
        icon = "✅" if status else "❌"
        print(f"{icon} {check_name}")
    
    if issues:
        print(f"\n⚠️ ПРОБЛЕМЫ ДЛЯ ИСПРАВЛЕНИЯ:")
        for issue in issues:
            print(issue)
    
    return passed, total, issues

# -------------------- ГЛАВНАЯ ФУНКЦИЯ --------------------
async def main_diagnostic():
    print("\n" + "🚀 ЗАПУСК ПОЛНОЙ ДИАГНОСТИКИ".center(80, "="))
    
    # Запуск проверок
    charting_ok = await check_charting_fixed()
    telegram_ok = await check_telegram()
    
    # Итоговая диагностика
    passed, total, issues = overall_health_check()
    
    print("\n" + "="*80)
    if passed == total and charting_ok and telegram_ok:
        print("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print(f"⚠️ НАЙДЕНЫ ПРОБЛЕМЫ ({total - passed} из {total} проверок не пройдены)")
    
    # Рекомендации
    print("\n📋 КРИТИЧЕСКИЕ ШАГИ ДЛЯ ИСПРАВЛЕНИЯ:")
    print("1. 📝 Отредактируйте файл .env и установите реальные значения:")
    print("   - TG_TOKEN или TELEGRAM_BOT_TOKEN (получите у @BotFather)")
    print("   - TG_CHAT_ID или TELEGRAM_CHAT_ID (используйте @getidsbot)")
    
    print("\n2. 🗄️ Создайте таблицу levels в базе данных:")
    print("   sqlite3 bot.db")
    print("   CREATE TABLE levels (")
    print("     id INTEGER PRIMARY KEY AUTOINCREMENT,")
    print("     symbol TEXT NOT NULL,")
    print("     tf TEXT NOT NULL,")
    print("     timestamp DATETIME,")
    print("     A REAL, C REAL, X REAL, F REAL")
    print("   );")
    
    print("\n3. 📦 Установите недостающие зависимости:")
    print("   pip install ta mplfinance")
    
    print("\n4. 🔧 Исправьте проблему с timestamp в свечах:")
    print("   Проверьте функцию fetch_kline в futures_bybit.py")
    print("   Убедитесь, что свечи содержат ключ 'timestamp' или 'time'")
    
    print("\n" + "="*80)

# -------------------- ЗАПУСК --------------------
if __name__ == "__main__":
    try:
        # Запускаем диагностику
        asyncio.run(main_diagnostic())
        
        # Краткий итог
        print("\n" + "📋 КРАТКИЙ ОТЧЕТ".center(80, "="))
        print("1. Проверьте .env файл (должны быть TG_TOKEN/TELEGRAM_BOT_TOKEN и TG_CHAT_ID/TELEGRAM_CHAT_ID)")
        print("2. Создайте таблицу levels в bot.db")
        print("3. Проверьте структуру данных в fetch_kline (должен быть ключ 'timestamp')")
        print("="*80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Диагностика прервана пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка при диагностике: {e}")
        traceback.print_exc()
    finally:
        print("\n" + "🏁 ДИАГНОСТИКА ЗАВЕРШЕНА".center(80, "="))