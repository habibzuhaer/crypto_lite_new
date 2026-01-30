# -*- coding: utf-8 -*-
import os, csv, sqlite3, time
from typing import List, Dict

def _connect(db_path: str = "bot.db") -> sqlite3.Connection:
    return sqlite3.connect(db_path, timeout=30)

async def export_csv(out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"ml_export_{int(time.time())}.csv")
    conn = _connect("bot.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, symbol, tf, side, entry, stop, tp1, tp2, tp3,
               qty, status, opened_at, closed_at, realized_pnl
        FROM paper_trades
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    header = [
        "id","symbol","tf","side","entry","stop",
        "tp1","tp2","tp3","qty","status",
        "opened_at","closed_at","realized_pnl"
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path
