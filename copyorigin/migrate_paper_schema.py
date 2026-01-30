# -*- coding: utf-8 -*-
import sqlite3, sys

DB_PATH = "bot.db"

NEEDED_COLS = [
    ("stop",         "REAL"),
    ("tp1",          "REAL"),
    ("tp2",          "REAL"),
    ("tp3",          "REAL"),
    ("qty",          "REAL"),
    ("status",       "TEXT DEFAULT 'open'"),
    ("opened_at",    "TEXT"),
    ("entered_at",   "TEXT"),
    ("closed_at",    "TEXT"),
    ("realized_pnl", "REAL DEFAULT 0.0"),
    ("last_price",   "REAL DEFAULT 0.0"),
    ("maker_fee",    "REAL DEFAULT 0.0"),
    ("taker_fee",    "REAL DEFAULT 0.0"),
]

def table_exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def get_cols(cur, table: str) -> set:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}

def main():
    con = sqlite3.connect(DB_PATH, timeout=30)
    cur = con.cursor()

    # если таблицы нет — создаём полную схему
    if not table_exists(cur, "paper_trades"):
        cur.execute("""
            CREATE TABLE paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                tf TEXT NOT NULL,
                side TEXT NOT NULL,
                entry REAL NOT NULL,
                stop REAL,
                tp1 REAL,
                tp2 REAL,
                tp3 REAL,
                qty REAL,
                status TEXT DEFAULT 'open',
                opened_at TEXT,
                entered_at TEXT,
                closed_at TEXT,
                realized_pnl REAL DEFAULT 0.0,
                last_price REAL DEFAULT 0.0,
                maker_fee REAL DEFAULT 0.0,
                taker_fee REAL DEFAULT 0.0
            )
        """)
        con.commit()
        con.close()
        print("created: paper_trades")
        return

    # если таблица есть — дублирующие ALTER не делаем
    existing = get_cols(cur, "paper_trades")
    added = []
    for name, typ in NEEDED_COLS:
        if name not in existing:
            cur.execute(f"ALTER TABLE paper_trades ADD COLUMN {name} {typ}")
            added.append(name)

    con.commit()
    con.close()
    print("added:", ",".join(added) if added else "(none)")

if __name__ == "__main__":
    main()
