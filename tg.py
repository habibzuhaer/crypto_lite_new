import aiohttp
import os
from loguru import logger
from typing import Optional

class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base = f"https://api.telegram.org/bot{token}"
        
        if not self.token:
            logger.error("TG_TOKEN не установлен")
        if not self.chat_id:
            logger.error("TG_CHAT_ID не установлен")
        else:
            logger.info(f"Telegram бот инициализирован для чата: {self.chat_id}")

    async def send_photo(self, photo_path: str, caption: Optional[str] = None) -> bool:
        """Отправка фото в Telegram"""
        # Проверка chat_id
        if not self.chat_id:
            logger.error("TG_CHAT_ID не установлен")
            return False
        
        # Проверка существования файла
        if not photo_path or not os.path.exists(photo_path):
            logger.error(f"Файл не существует: {photo_path}")
            return False
        
        # Проверка размера файла
        try:
            file_size = os.path.getsize(photo_path)
            if file_size == 0:
                logger.error(f"Файл пустой: {photo_path}")
                return False
        except Exception as e:
            logger.error(f"Ошибка получения размера файла {photo_path}: {e}")
            return False
        
        # Обработка caption
        if caption is None:
            caption = ""
        else:
            caption = str(caption)[:1024]  # Ограничиваем длину
        
        url = f"{self.base}/sendPhoto"
        
        try:
            # В Linux нужно читать файл в байты до создания FormData
            photo_bytes = None
            with open(photo_path, 'rb') as f:
                photo_bytes = f.read()
            
            # Создаем FormData
            form = aiohttp.FormData()
            
            # Добавляем chat_id
            form.add_field('chat_id', str(self.chat_id))
            
            # Добавляем фото как байты
            form.add_field(
                'photo', 
                photo_bytes,
                filename=os.path.basename(photo_path),
                content_type='image/png'
            )
            
            # Добавляем caption если не пустой
            if caption:
                form.add_field('caption', caption)
            
            # Отправляем запрос с увеличенным таймаутом
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(url, data=form) as response:
                    if response.status == 200:
                        logger.success(f"Фото успешно отправлено: {os.path.basename(photo_path)}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка отправки фото: {response.status} - {error_text}")
                        return False
                        
        except FileNotFoundError:
            logger.error(f"Файл не найден: {photo_path}")
            return False
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    async def send_message(self, text: str, parse_mode: Optional[str] = 'HTML', **kwargs) -> bool:
        """Отправка текстового сообщения в Telegram"""
        if not self.chat_id:
            logger.error("TG_CHAT_ID не установлен")
            return False
        
        url = f"{self.base}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode  # Используем переданный parse_mode или 'HTML' по умолчанию
        }
        
        # Обрабатываем дополнительные параметры, которые могут быть полезны
        # Игнорируем неподдерживаемые параметры, но логируем предупреждение
        supported_params = ['disable_web_page_preview', 'disable_notification', 'reply_to_message_id']
        for param in supported_params:
            if param in kwargs:
                payload[param] = kwargs[param]
        
        # Логируем неподдерживаемые параметры (но не падаем)
        for key in kwargs:
            if key not in supported_params and key != 'parse_mode':
                logger.warning(f"Неподдерживаемый параметр в send_message: {key} (игнорируется)")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка отправки сообщения: {response.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False