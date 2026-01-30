# -*- coding: utf-8 -*-
import os, hmac, hashlib, time, aiohttp, asyncio
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

async def signed(session, endpoint, params=None):
    if params is None:
        params = {}
    params["api_key"] = API_KEY
    params["timestamp"] = int(time.time() * 1000)
    params["recv_window"] = 5000
    sign_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    signature = hmac.new(API_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    params["sign"] = signature
    url = f"https://api.bybit.com{endpoint}"
    async with session.get(url, params=params) as r:
        try:
            return await r.json()
        except Exception:
            txt = await r.text()
            return {"raw": txt, "status": r.status}

async def main():
    print("=== BYBIT API DIAGNOSTICS (FULL) ===")
    if not API_KEY or not API_SECRET:
        print("❌ Ключи не найдены в .env")
        return

    async with aiohttp.ClientSession() as s:
        # 1. Проверка соединения
        try:
            r = await s.get("https://api.bybit.com/v5/public/time")
            txt = await r.text()
            print("✅ Сеть OK — server-time:", txt.strip())
        except Exception as e:
            print("❌ Ошибка сети:", e)
            return

        # 2. Проверка авторизации
        try:
            acc = await signed(s, "/v5/account/info")
            if acc.get("retCode") == 0:
                print("✅ Авторизация успешна — account/info OK")
            else:
                print("❌ Ошибка авторизации:", acc)
        except Exception as e:
            print("❌ Ошибка account/info:", e)

        # 3. Проверка баланса
        try:
            bal = await signed(s, "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
            if bal.get("retCode") == 0:
                coins = bal["result"]["list"][0]["coin"]
                usdt = next((c for c in coins if c["coin"] == "USDT"), None)
                if usdt:
                    print(f"✅ Баланс USDT: {usdt['walletBalance']}")
                else:
                    print("⚠️ Баланс USDT не найден:", coins)
            else:
                print("❌ Ошибка баланса:", bal)
        except Exception as e:
            print("❌ Ошибка wallet-balance:", e)

        # 4. Проверка позиций
        try:
            pos = await signed(s, "/v5/position/list", {"category": "linear"})
            if pos.get("retCode") == 0:
                n = len(pos["result"]["list"])
                print(f"✅ Позиции: {n} активных")
            else:
                print("❌ Ошибка позиций:", pos)
        except Exception as e:
            print("❌ Ошибка position/list:", e)

    print("=== END ===")

asyncio.run(main())
