# -*- coding: utf-8 -*-
import sqlite3, time

DB_PATH = "bot.db"

SCHEMA_SQL = """
CREATE TABLE paper_trades_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    tf          TEXT NOT NULL,
    side        TEXT NOT NULL,              -- 'long' | 'short'
    entry       REAL NOT NULL,
    stop        REAL NOT NULL,
    tp1         REAL NOT NULL,
    tp2         REAL NOT NULL,
    tp3         REAL NOT NULL,
    qty         REAL NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',
    opened_at   TEXT NOT NULL,
    entered_at  TEXT NOT NULL,
    closed_at   TEXT,
    realized_pnl REAL NOT NULL DEFAULT 0.0,
    last_price   REAL NOT NULL DEFAULT 0.0,
    maker_fee    REAL NOT NULL DEFAULT 0.0,
    taker_fee    REAL NOT NULL DEFAULT 0.0
);
"""

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

def get_cols(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}

def main():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Проверка наличия старой таблицы
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='paper_trades'")
    if not cur.fetchone():
        # Если таблицы нет — создаём новую с нуля
        cur.executescript(SCHEMA_SQL)
        con.commit()
        cur.execute("ALTER TABLE paper_trades_new RENAME TO paper_trades")
        con.commit()
        con.close()
        print("created: paper_trades (fresh)")
        return

    # Считываем старые строки
    cur.execute("SELECT * FROM paper_trades")
    old_rows = cur.fetchall()
    old_cols = get_cols(cur, "paper_trades")

    # Создаём новую таблицу с целевой схемой
    cur.executescript(SCHEMA_SQL)
    con.commit()

    # Переносим данные с маппингом sl->stop и дефолтами
    ins = """
        INSERT INTO paper_trades_new
        (id, symbol, tf, side, entry, stop, tp1, tp2, tp3, qty, status,
         opened_at, entered_at, closed_at, realized_pnl, last_price, maker_fee, taker_fee)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    moved = 0
    for r in old_rows:
        # Обязательные
        symbol = r["symbol"] if "symbol" in old_cols else "UNKNOWN"
        tf     = r["tf"]     if "tf"     in old_cols else "0"
        side   = r["side"]   if "side"   in old_cols else "long"
        entry  = float(r["entry"]) if "entry" in old_cols and r["entry"] is not None else 0.0

        # stop: берём stop, иначе sl, иначе 0.0
        stop = None
        if "stop" in old_cols and r["stop"] is not None:
            stop = float(r["stop"])
        elif "sl" in old_cols and r["sl"] is not None:
            stop = float(r["sl"])
        else:
            stop = 0.0

        tp1 = float(r["tp1"]) if "tp1" in old_cols and r["tp1"] is not None else 0.0
        tp2 = float(r["tp2"]) if "tp2" in old_cols and r["tp2"] is not None else 0.0
        tp3 = float(r["tp3"]) if "tp3" in old_cols and r["tp3"] is not None else 0.0

        # qty: если был — берём, иначе простой дефолт 1.5
        qty = float(r["qty"]) if "qty" in old_cols and r["qty"] is not None else 1.5

        status = r["status"] if "status" in old_cols and r["status"] else "open"
        opened_at  = r["opened_at"]  if "opened_at"  in old_cols and r["opened_at"]  else now()
        entered_at = r["entered_at"] if "entered_at" in old_cols and r["entered_at"] else opened_at
        closed_at  = r["closed_at"]  if "closed_at"  in old_cols and r["closed_at"]  else None

        realized_pnl = float(r["realized_pnl"]) if "realized_pnl" in old_cols and r["realized_pnl"] is not None else 0.0
        last_price   = float(r["last_price"])   if "last_price"   in old_cols and r["last_price"]   is not None else (entry or 0.0)
        maker_fee    = float(r["maker_fee"])    if "maker_fee"    in old_cols and r["maker_fee"]    is not None else 0.0
        taker_fee    = float(r["taker_fee"])    if "taker_fee"    in old_cols and r["taker_fee"]    is not None else 0.0

        cur.execute(ins, (
            r["id"] if "id" in old_cols else None,
            symbol, tf, side, entry, stop, tp1, tp2, tp3, qty, status,
            opened_at, entered_at, closed_at, realized_pnl, last_price, maker_fee, taker_fee
        ))
        moved += 1

    con.commit()

    # Переключаем таблицы
    cur.execute("DROP TABLE paper_trades")
    cur.execute("ALTER TABLE paper_trades_new RENAME TO paper_trades")
    con.commit()
    con.close()
    print(f"migrated: {moved} rows")

if __name__ == "__main__":
    main()
