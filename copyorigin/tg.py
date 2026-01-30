# -*- coding: utf-8 -*-
import os, aiohttp, asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

class TGQ:
    def __init__(self):
        self.token = TOKEN
        self.chat_id = CHAT_ID
        self.base = f"https://api.telegram.org/bot{self.token}"

    async def send_text(self, text: str, kb=None) -> bool:
        url = f"{self.base}/sendMessage"
        data = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        async with aiohttp.ClientSession() as s:
            async with s.post(url, data=data) as r:
                return r.status == 200

    async def send_photo(self, photo_path: str, caption: str = "", kb=None) -> bool:
        if not os.path.exists(photo_path):
            return False
        url = f"{self.base}/sendPhoto"
        data = {"chat_id": self.chat_id, "caption": caption, "parse_mode": "HTML"}
        async with aiohttp.ClientSession() as s:
            with open(photo_path, "rb") as f:
                form = aiohttp.FormData()
                form.add_field("photo", f, filename=os.path.basename(photo_path))
                for k, v in data.items():
                    form.add_field(k, v)
                async with s.post(url, data=form) as r:
                    return r.status == 200

async def get_updates(offset: int | None = None) -> list[dict]:
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"offset": offset} if offset else {}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params=params) as r:
            if r.status == 200:
                js = await r.json()
                return js.get("result", [])
            return []

def kb_main() -> dict:
    return {"keyboard": [[{"text": "Обновить"}]], "resize_keyboard": True}
