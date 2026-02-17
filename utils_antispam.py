# utils_antispam.py
import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, Set, Tuple, Optional, Any, Callable
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# ========== СТАРИЙ ФУНКЦІОНАЛ (НЕ ЧІПАЄМО) ==========

class AntiSpamManager:
    """
    Оригінальний клас для захисту від частих викликів функцій.
    Залишаємо без змін.
    """
    def __init__(self):
        # Хранилище: {user_id: {"count": int, "first_call": timestamp}}
        self.call_limits: Dict[int, Dict] = {}
        self.spam_words: Set[str] = {"spam", "ad", "http://", "https://"}  # можно расширить
        self.user_ban_until: Dict[int, datetime] = {}  # {user_id: datetime до которого забанен}
        
    def is_spam_text(self, text: str) -> bool:
        """Перевіряє, чи містить текст спам-слова."""
        text_lower = text.lower()
        for word in self.spam_words:
            if word in text_lower:
                return True
        return False
    
    def check_rate_limit(self, user_id: int, limit: int = 5, period: int = 60) -> Tuple[bool, int]:
        """
        Перевіряє ліміт викликів для користувача.
        Повертає (is_limited, calls_count)
        """
        now = time.time()
        
        if user_id not in self.call_limits:
            self.call_limits[user_id] = {"count": 1, "first_call": now}
            return False, 1
            
        user_data = self.call_limits[user_id]
        time_diff = now - user_data["first_call"]
        
        if time_diff > period:
            # Скидаємо лічильник після закінчення періоду
            self.call_limits[user_id] = {"count": 1, "first_call": now}
            return False, 1
        
        user_data["count"] += 1
        
        if user_data["count"] > limit:
            return True, user_data["count"]
            
        return False, user_data["count"]
    
    def ban_user(self, user_id: int, minutes: int = 10):
        """Банить користувача на вказаний час."""
        ban_until = datetime.now() + timedelta(minutes=minutes)
        self.user_ban_until[user_id] = ban_until
        logger.warning(f"User {user_id} banned until {ban_until}")
    
    def is_user_banned(self, user_id: int) -> bool:
        """Перевіряє, чи забанений користувач."""
        if user_id in self.user_ban_until:
            if datetime.now() < self.user_ban_until[user_id]:
                return True
            else:
                # Видаляємо прострочений бан
                del self.user_ban_until[user_id]
        return False
    
    def clear_old(self):
        """Очищає старі записи лімітів."""
        now = time.time()
        to_delete = []
        for user_id, data in self.call_limits.items():
            if now - data["first_call"] > 3600:  # старше години
                to_delete.append(user_id)
        for user_id in to_delete:
            del self.call_limits[user_id]


# ========== НОВИЙ ФУНКЦІОНАЛ (ДЛЯ ТЕЛЕГРАМ СИГНАЛІВ) ==========

class SignalAntiSpam:
    """
    Новий клас для захисту від дублікатів сигналів у Telegram.
    """
    def __init__(self):
        # Зберігаємо останні сигнали: {ключ: {"text": str, "timestamp": float, "count": int}}
        self.sent_signals = defaultdict(dict)
        # Час, після якого сигнал можна надсилати заново (в секундах)
        self.cooldown = 300  # 5 хвилин
        # Максимальна кількість однакових сигналів поспіль
        self.max_repeats = 2
        # Мінімальна зміна ціни для нового сигналу (у відсотках)
        self.min_price_change = 0.001  # 0.1%
        
    def is_duplicate_signal(self, signal_key: str, signal_text: str, current_price: float = None) -> bool:
        """
        Перевіряє, чи є сигнал дублікатом.
        Повертає True, якщо сигнал треба заблокувати.
        """
        now = time.time()
        signal_data = self.sent_signals.get(signal_key)
        
        # Новий сигнал (ніколи не надсилали)
        if not signal_data:
            return False
            
        # Перевірка за часом
        time_diff = now - signal_data.get("timestamp", 0)
        if time_diff > self.cooldown:
            return False  # Минуло достатньо часу, можна надсилати заново
            
        # Перевірка на точний збіг тексту
        if signal_data.get("text") == signal_text:
            # Збільшуємо лічильник повторів
            signal_data["count"] = signal_data.get("count", 1) + 1
            if signal_data["count"] >= self.max_repeats:
                logger.debug(f"Signal {signal_key}: too many repeats ({signal_data['count']})")
                return True
            return True
            
        # Якщо текст різний, але є ціна - перевіряємо зміну
        if current_price is not None and "price" in signal_data:
            old_price = signal_data["price"]
            price_change = abs(current_price - old_price) / old_price
            if price_change < self.min_price_change:
                logger.debug(f"Signal {signal_key}: price change too small ({price_change:.4%})")
                return True
                
        return False
    
    def remember_signal(self, signal_key: str, signal_text: str, price: float = None):
        """
        Запам'ятовує надісланий сигнал.
        """
        self.sent_signals[signal_key] = {
            "text": signal_text,
            "timestamp": time.time(),
            "count": 1,
            "price": price
        }
        logger.debug(f"Signal {signal_key} remembered")
    
    def clear_old_signals(self, max_age: int = 86400):
        """
        Видаляє старі сигнали (старше max_age секунд).
        """
        now = time.time()
        to_delete = []
        for key, data in self.sent_signals.items():
            if now - data.get("timestamp", 0) > max_age:
                to_delete.append(key)
        
        for key in to_delete:
            del self.sent_signals[key]
        
        if to_delete:
            logger.debug(f"Cleared {len(to_delete)} old signals")
    
    def set_cooldown(self, seconds: int):
        """Змінює час між сигналами."""
        self.cooldown = seconds
        
    def set_price_threshold(self, percent: float):
        """Змінює мінімальну зміну ціни для нового сигналу."""
        self.min_price_change = percent / 100  # переводимо відсотки у десятковий дріб


# ========== ОБ'ЄДНАНІ ДЕКОРАТОРИ ==========

# Глобальні екземпляри для зручності
spam_manager = AntiSpamManager()
signal_spam = SignalAntiSpam()


def rate_limit(limit: int = 5, period: int = 60):
    """
    Декоратор для обмеження частоти викликів функції (старий функціонал).
    Використання: @rate_limit(limit=10, period=120)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Спроба отримати user_id з аргументів
            user_id = None
            if args and isinstance(args[0], int):
                user_id = args[0]
            elif 'user_id' in kwargs:
                user_id = kwargs['user_id']
            
            if user_id is not None:
                is_limited, count = spam_manager.check_rate_limit(user_id, limit, period)
                if is_limited:
                    logger.warning(f"Rate limit exceeded for user {user_id}")
                    return None, f"Перевищено ліміт запитів. Спробуйте пізніше."
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def prevent_signal_spam(func: Callable):
    """
    НОВИЙ декоратор для захисту від спаму сигналами.
    Використовувати для функцій, які надсилають сигнали в Telegram.
    """
    @wraps(func)
    def wrapper(symbol: str, signal_type: str, price: float, timeframe: str, *args, **kwargs):
        # Формуємо ключ сигналу
        signal_key = f"{symbol}_{timeframe}"
        
        # Формуємо текст сигналу (можна передати готовий або створити)
        message_text = kwargs.get('message_text')
        if not message_text:
            message_text = f"#{symbol}\n{signal_type}\nЦіна: {price}\nТФ: {timeframe}"
        
        # Перевіряємо на дублікат
        if signal_spam.is_duplicate_signal(signal_key, message_text, price):
            logger.info(f"Signal {signal_key} blocked by anti-spam")
            return False
        
        # Викликаємо оригінальну функцію
        result = func(symbol, signal_type, price, timeframe, *args, **kwargs)
        
        # Якщо надсилання успішне - запам'ятовуємо сигнал
        if result:  # вважаємо, що функція повертає True при успіху
            signal_spam.remember_signal(signal_key, message_text, price)
        
        return result
    return wrapper


# ========== ДОДАТКОВІ УТИЛІТИ ==========

def setup_antispam_logging():
    """Налаштовує логування для антиспаму."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


# Для сумісності зі старим кодом експортуємо основні функції
__all__ = [
    'AntiSpamManager',
    'SignalAntiSpam',
    'spam_manager',
    'signal_spam',
    'rate_limit',
    'prevent_signal_spam',
    'setup_antispam_logging'
]