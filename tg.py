#!/usr/bin/env python3
"""
TG - Модуль для отправки структурированных оповещений в Telegram
с интеграцией антиспам-защиты
"""

import asyncio
import aiohttp
import os
from typing import Optional, Dict, List, Tuple, Any
import logging
from datetime import datetime

# Импортируем антиспам (ВНИМАНИЕ: импорт после настроек логирования)
from utils_antispam import signal_spam

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Константы Telegram API
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"

class TelegramBot:
    """Класс для работы с Telegram Bot API."""
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.session = None
        
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN не установлен")
        if not self.chat_id:
            logger.warning("TELEGRAM_CHAT_ID не установлен")
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Базовый метод для запросов к Telegram API."""
        if not self.token:
            logger.error("Токен бота не установлен")
            return None
        
        url = TELEGRAM_API_URL.format(token=self.token, method=method)
        
        try:
            async with self.session.post(url, json=params) as response:
                if response.status != 200:
                    logger.error(f"HTTP ошибка: {response.status}")
                    return None
                
                data = await response.json()
                if not data.get("ok"):
                    logger.error(f"Telegram API error: {data.get('description')}")
                    return None
                
                return data.get("result")
        except Exception as e:
            logger.error(f"Ошибка при запросе к Telegram API: {e}")
            return None
    
    async def send_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        disable_web_page_preview: bool = True,
        disable_notification: bool = False
    ) -> bool:
        """Отправка текстового сообщения в чат, указанный в chat_id."""
        if not self.chat_id:
            logger.error("Chat ID не установлен")
            return False
        
        params = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
            "disable_notification": disable_notification
        }
        
        result = await self._make_request("sendMessage", params)
        success = result is not None
        
        if success:
            logger.info(f"Сообщение отправлено в чат {self.chat_id}")
        else:
            logger.error(f"Не удалось отправить сообщение в чат {self.chat_id}")
        
        return success


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ АНТИСПАМА
# ============================================================================

def _get_signal_key(symbol: str, tf: str, report_type: str) -> str:
    """
    Формирует ключ для антиспама на основе символа, таймфрейма и типа отчета.
    Пример: "BTCUSDT_1h_levels"
    """
    return f"{symbol}_{tf}_{report_type}"


def _extract_price_from_message(message: str) -> Optional[float]:
    """
    Пытается извлечь цену из текста сообщения для проверки изменений.
    Ищет паттерн "Текущая цена: `12345.67`" или аналогичный.
    """
    import re
    # Ищем число после "Текущая цена: `" или "💰 Текущая цена: `"
    price_pattern = r'Текущая цена:.*?`(\d+\.?\d*)`'
    match = re.search(price_pattern, message)
    if match:
        return float(match.group(1))
    return None


# ============================================================================
# ОСНОВНЫЕ ФУНКЦИИ ДЛЯ ОТПРАВКИ ОПОВЕЩЕНИЙ (ИМПОРТИРУЮТСЯ В MAIN)
# ============================================================================

async def send_levels_report(symbol: str, tf: str, levels: List[float], current_price: float) -> bool:
    """
    Отправляет отчёт о рассчитанных уровнях для заданного символа и таймфрейма.
    Используется для MTF и STF.
    """
    if not levels:
        return True  # Нет уровней - не отправляем пустое сообщение
    
    # Сортируем уровни для удобства чтения
    sorted_levels = sorted(levels)
    
    # Формируем списки поддержки и сопротивления относительно текущей цены
    support_levels = [lvl for lvl in sorted_levels if lvl < current_price]
    resistance_levels = [lvl for lvl in sorted_levels if lvl > current_price]
    
    # Создаём текст сообщения
    message = f"""
📊 *Уровни {symbol} | {tf}*
──────────────────────
💰 Текущая цена: `{current_price:.2f}`

⬇️ *Уровни поддержки:*
"""
    
    # Добавляем уровни поддержки (сверху вниз - от ближнего к дальнему)
    for level in reversed(support_levels[-5:]):  # Последние 5 уровней поддержки
        diff_percent = ((current_price - level) / current_price) * 100
        message += f"• `{level:.2f}` (-{diff_percent:.2f}%)\n"
    
    message += "\n⬆️ *Уровни сопротивления:*\n"
    
    # Добавляем уровни сопротивления (снизу вверх - от ближнего к дальнему)
    for level in resistance_levels[:5]:  # Первые 5 уровней сопротивления
        diff_percent = ((level - current_price) / current_price) * 100
        message += f"• `{level:.2f}` (+{diff_percent:.2f}%)\n"
    
    message += f"""
──────────────────────
📈 Всего уровней: {len(levels)}
⏰ {datetime.now().strftime('%H:%M:%S')}
    """
    
    # ===== АНТИСПАМ: проверка на дубликат =====
    signal_key = _get_signal_key(symbol, tf, "levels")
    
    if signal_spam.is_duplicate_signal(signal_key, message, current_price):
        logger.info(f"[ANTISPAM] Уровни {signal_key} заблокированы (дубликат)")
        return False
    
    # Отправляем сообщение
    async with TelegramBot() as bot:
        success = await bot.send_message(message)
    
    # ===== АНТИСПАМ: запоминаем успешную отправку =====
    if success:
        signal_spam.remember_signal(signal_key, message, current_price)
        logger.info(f"[ANTISPAM] Уровни {signal_key} запомнены")
    
    return success


async def send_margin_zones_report(symbol: str, tf: str, zones: List[Dict[str, float]], current_price: float) -> bool:
    """
    Отправляет отчёт о маржинальных зонах для заданного символа и таймфрейма.
    Используется ТОЛЬКО для STF (1h, 4h).
    """
    if not zones:
        return True  # Нет зон - не отправляем пустое сообщение
    
    # Сортируем зоны по средней точке для удобства чтения
    sorted_zones = sorted(zones, key=lambda z: (z['high'] + z['low']) / 2)
    
    # Формируем текст сообщения
    message = f"""
🎯 *Маржинальные зоны {symbol} | {tf}*
──────────────────────
💰 Текущая цена: `{current_price:.2f}`

📏 *Обнаруженные зоны ликвидности:*
"""
    
    for i, zone in enumerate(sorted_zones, 1):
        zone_low = zone['low']
        zone_high = zone['high']
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
{i}. *Диапазон:* `{zone_low:.2f}` - `{zone_high:.2f}`
   *Средняя:* `{zone_mid:.2f}`
   *Ширина:* {zone_width_percent:.2f}%
   *Положение:* {position}
"""
    
    message += f"""
──────────────────────
📊 Всего зон: {len(zones)}
⏰ {datetime.now().strftime('%H:%M:%S')}
    """
    
    # ===== АНТИСПАМ: проверка на дубликат =====
    signal_key = _get_signal_key(symbol, tf, "margin_zones")
    
    if signal_spam.is_duplicate_signal(signal_key, message, current_price):
        logger.info(f"[ANTISPAM] Маржинальные зоны {signal_key} заблокированы (дубликат)")
        return False
    
    # Отправляем сообщение
    async with TelegramBot() as bot:
        success = await bot.send_message(message)
    
    # ===== АНТИСПАМ: запоминаем успешную отправку =====
    if success:
        signal_spam.remember_signal(signal_key, message, current_price)
        logger.info(f"[ANTISPAM] Маржинальные зоны {signal_key} запомнены")
    
    return success


async def send_collision_alert(
    symbol: str, 
    tf: str, 
    level: float, 
    zone: Dict[str, float], 
    current_price: float
) -> bool:
    """
    Отправляет СПЕЦИАЛЬНОЕ оповещение о совпадении уровня и маржинальной зоны.
    Используется ТОЛЬКО для STF (1h, 4h) при обнаружении совпадения.
    """
    zone_low = zone['low']
    zone_high = zone['high']
    
    # Вычисляем, насколько уровень близок к границам зоны
    if level < zone_low:
        distance_to_zone = zone_low - level
        distance_percent = (distance_to_zone / level) * 100
        position = f"ниже нижней границы на {distance_percent:.3f}%"
    elif level > zone_high:
        distance_to_zone = level - zone_high
        distance_percent = (distance_to_zone / level) * 100
        position = f"выше верхней границы на {distance_percent:.3f}%"
    else:
        distance_to_center = abs(level - (zone_low + zone_high) / 2)
        distance_percent = (distance_to_center / level) * 100
        position = f"внутри зоны (от центра {distance_percent:.3f}%)"
    
    # Формируем текст сообщения с ЖЁЛТЫМ ТРЕУГОЛЬНИКОМ в начале
    message = f"""
⚠️ *СОВПАДЕНИЕ! {symbol} | {tf}*
──────────────────────
🎯 Уровень `{level:.2f}` находится в зоне маржинальных требований!

📏 *Детали зоны:*
• Нижняя граница: `{zone_low:.2f}`
• Верхняя граница: `{zone_high:.2f}`
• Ширина: {((zone_high - zone_low) / zone_low * 100):.2f}%

📊 *Характеристика совпадения:*
• Уровень {position}
• Расстояние до ближайшей границы: {min(abs(level-zone_low), abs(level-zone_high)):.2f}
• Текущая цена: `{current_price:.2f}`

💡 *Интерпретация:*
Это зона повышенного интереса, где могут активироваться крупные ордера.
Совпадение с техническим уровнем усиливает её значимость.

──────────────────────
⏰ {datetime.now().strftime('%H:%M:%S')}
    """
    
    # ===== АНТИСПАМ: проверка на дубликат =====
    signal_key = _get_signal_key(symbol, tf, "collision")
    
    # Для коллизий используем более жесткие настройки (меньше повторений)
    # Сохраняем оригинальные настройки
    original_cooldown = signal_spam.cooldown
    original_max_repeats = signal_spam.max_repeats
    
    # Временно увеличиваем защиту для коллизий
    signal_spam.cooldown = 600  # 10 минут вместо 5
    signal_spam.max_repeats = 1  # Только один раз
    
    is_duplicate = signal_spam.is_duplicate_signal(signal_key, message, current_price)
    
    # Возвращаем настройки
    signal_spam.cooldown = original_cooldown
    signal_spam.max_repeats = original_max_repeats
    
    if is_duplicate:
        logger.info(f"[ANTISPAM] Коллизия {signal_key} заблокирована (дубликат)")
        return False
    
    # Отправляем сообщение (уведомление включено)
    async with TelegramBot() as bot:
        success = await bot.send_message(message, disable_notification=False)
    
    # ===== АНТИСПАМ: запоминаем успешную отправку =====
    if success:
        signal_spam.remember_signal(signal_key, message, current_price)
        logger.info(f"[ANTISPAM] Коллизия {signal_key} запомнена")
    
    return success


async def test_bot_connection() -> bool:
    """
    Тестирование подключения к боту.
    """
    async with TelegramBot() as bot:
        test_params = {
            "chat_id": bot.chat_id,
            "text": "🤖 Бот подключен и готов к работе!",
            "parse_mode": "Markdown"
        }
        
        result = await bot._make_request("sendMessage", test_params)
        
        if result:
            logger.info("✅ Тест подключения к Telegram пройден успешно")
            return True
        else:
            logger.error("❌ Не удалось подключиться к Telegram боту")
            return False


# ============================================================================
# ТЕСТИРОВАНИЕ МОДУЛЯ С УЧЕТОМ АНТИСПАМА
# ============================================================================
async def test_all_reports():
    """Функция для тестирования всех типов оповещений."""
    print("🧪 Тестирование модуля Telegram с антиспамом...")
    
    if not await test_bot_connection():
        print("❌ Не удалось подключиться к боту")
        return
    
    # Тестовые данные
    symbol = "BTCUSDT"
    tf = "1h"
    current_price = 45000.0
    test_levels = [44800.0, 44950.0, 45200.0, 45500.0, 45800.0]
    test_zones = [
        {'high': 44980.0, 'low': 44920.0, 'width': 60.0, 'strength': 0.8},
        {'high': 45300.0, 'low': 45200.0, 'width': 100.0, 'strength': 0.9}
    ]
    
    print("\n🔄 Тест 1: Отправка уровней (должна пройти)...")
    result1 = await send_levels_report(symbol, tf, test_levels, current_price)
    print(f"   Результат: {'✅ Успешно' if result1 else '❌ Блок'}")

    print("\n🔄 Тест 2: Повторная отправка уровней (должна быть заблокирована антиспамом)...")
    result2 = await send_levels_report(symbol, tf, test_levels, current_price)
    print(f"   Результат: {'✅ Успешно' if result2 else '❌ Блок (ОК)'}")
    
    print("\n🔄 Тест 3: Отправка уровней с другой ценой (должна пройти)...")
    result3 = await send_levels_report(symbol, tf, test_levels, 45100.0)  # Цена изменилась
    print(f"   Результат: {'✅ Успешно' if result3 else '❌ Блок'}")
    
    print("\n🔄 Тест 4: Отправка маржинальных зон...")
    result4 = await send_margin_zones_report(symbol, tf, test_zones, current_price)
    print(f"   Результат: {'✅ Успешно' if result4 else '❌ Блок'}")
    
    print("\n🔄 Тест 5: Отправка коллизии...")
    result5 = await send_collision_alert(symbol, tf, 44950.0, test_zones[0], current_price)
    print(f"   Результат: {'✅ Успешно' if result5 else '❌ Блок'}")
    
    print("\n🔄 Тест 6: Повторная отправка коллизии (должна быть заблокирована)...")
    result6 = await send_collision_alert(symbol, tf, 44950.0, test_zones[0], current_price)
    print(f"   Результат: {'✅ Успешно' if result6 else '❌ Блок (ОК)'}")
    
    print("\n✅ Тестирование завершено")
    
    # Показываем статистику антиспама
    print("\n📊 Статистика антиспама:")
    print(f"   Всего запомнено сигналов: {len(signal_spam.sent_signals)}")
    for key, data in signal_spam.sent_signals.items():
        print(f"   • {key}: {data.get('count', 0)} раз(а)")


if __name__ == "__main__":
    asyncio.run(test_all_reports())