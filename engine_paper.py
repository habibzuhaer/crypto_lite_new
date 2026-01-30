# -*- coding: utf-8 -*-
import sqlite3, time
from typing import List, Dict, Any, Optional

DB_PATH   = "bot.db"
USD_SIZE  = 50.0     # размер позиции в USDT
LEVERAGE  = 3.0      # плечо X3
FEE_RATE  = 0.0006   # комиссия по умолчанию (0.06%)

# ------------------------- DB ------------------------- #
def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, timeout=30)
    con.row_factory = sqlite3.Row
    return con

def _ensure_schema(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            tf TEXT NOT NULL,
            side TEXT NOT NULL,          -- 'long' | 'short'
            entry REAL NOT NULL,
            stop REAL NOT NULL,
            tp1 REAL NOT NULL,
            tp2 REAL NOT NULL,
            tp3 REAL NOT NULL,
            qty REAL NOT NULL,
            status TEXT NOT NULL,        -- 'open' | 'tp1' | 'tp2' | 'tp3' | 'stop' | 'cancel'
            opened_at TEXT NOT NULL,
            entered_at TEXT NOT NULL,
            closed_at TEXT,
            realized_pnl REAL NOT NULL DEFAULT 0.0,
            last_price REAL NOT NULL DEFAULT 0.0,
            maker_fee REAL NOT NULL DEFAULT 0.0,
            taker_fee REAL NOT NULL DEFAULT 0.0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS balance (
            id INTEGER PRIMARY KEY CHECK (id=1),
            amount REAL
        )
    """)
    cur.execute("INSERT OR IGNORE INTO balance (id, amount) VALUES (1, 1000.0)")
    con.commit()

# ---------------------- HELPERS ----------------------- #
def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}

def _calc_qty(entry: float, usd: float = USD_SIZE, lev: float = LEVERAGE) -> float:
    if entry <= 0:
        return 0.0
    return round((usd * lev) / entry, 6)

# ---------------------- PAPER API --------------------- #
def place_signal(db_path: str, symbol: str, tf: str, side: str,
                 entry: float, stop: float,
                 tp1: float, tp2: float, tp3: float) -> int:
    """Создать бумажную сделку (status='open'), qty вычисляется от USD_SIZE и LEVERAGE."""
    con = _connect(db_path)
    _ensure_schema(con)
    qty = _calc_qty(entry)
    opened = _now()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO paper_trades
        (symbol, tf, side, entry, stop, tp1, tp2, tp3, qty, status,
         opened_at, entered_at, last_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
    """, (symbol, tf, side, entry, stop, tp1, tp2, tp3, qty, opened, opened, entry))
    tid = cur.lastrowid
    con.commit()
    con.close()
    return tid

def on_tick(db_path: str, symbol: str, price: float, fee_rate: float = FEE_RATE) -> None:
    """Обновить состояние открытых сделок по символу по текущей цене (tp/stop)."""
    con = _connect(db_path)
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute("""
        SELECT id, side, entry, stop, tp1, tp2, tp3, qty, status
        FROM paper_trades
        WHERE symbol=? AND status='open'
    """, (symbol,))
    rows = cur.fetchall()

    for r in rows:
        tid, side, entry, stop, tp1, tp2, tp3, qty, status = (
            r["id"], r["side"], r["entry"], r["stop"], r["tp1"], r["tp2"], r["tp3"], r["qty"], r["status"]
        )
        maker_fee = entry * qty * fee_rate
        taker_fee = price * qty * fee_rate

        closed = False
        new_status = status
        pnl = 0.0

        if side == "long":
            if price <= stop:
                pnl = (stop - entry) * qty - maker_fee - taker_fee
                new_status = "stop"; closed = True
            elif price >= tp3:
                pnl = (tp3 - entry) * qty - maker_fee - taker_fee
                new_status = "tp3"; closed = True
            elif price >= tp2:
                pnl = (tp2 - entry) * qty - maker_fee - taker_fee
                new_status = "tp2"; closed = True
            elif price >= tp1:
                pnl = (tp1 - entry) * qty - maker_fee - taker_fee
                new_status = "tp1"; closed = True
        else:  # short
            if price >= stop:
                pnl = (entry - stop) * qty - maker_fee - taker_fee
                new_status = "stop"; closed = True
            elif price <= tp3:
                pnl = (entry - tp3) * qty - maker_fee - taker_fee
                new_status = "tp3"; closed = True
            elif price <= tp2:
                pnl = (entry - tp2) * qty - maker_fee - taker_fee
                new_status = "tp2"; closed = True
            elif price <= tp1:
                pnl = (entry - tp1) * qty - maker_fee - taker_fee
                new_status = "tp1"; closed = True

        if closed:
            cur.execute("""
                UPDATE paper_trades
                SET status=?, closed_at=?, realized_pnl=?, last_price=?,
                    maker_fee=?, taker_fee=?
                WHERE id=?
            """, (new_status, _now(), pnl, price, maker_fee, taker_fee, tid))
        else:
            cur.execute("""
                UPDATE paper_trades
                SET last_price=?
                WHERE id=?
            """, (price, tid))

    con.commit()
    con.close()

def get_open_trades(db_path: str) -> List[Dict[str, Any]]:
    con = _connect(db_path)
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute("SELECT * FROM paper_trades WHERE status='open' ORDER BY id DESC")
    rows = [ _row_to_dict(r) for r in cur.fetchall() ]
    con.close()
    return rows

def get_history(db_path: str) -> List[Dict[str, Any]]:
    con = _connect(db_path)
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute("SELECT * FROM paper_trades WHERE status!='open' ORDER BY id DESC")
    rows = [ _row_to_dict(r) for r in cur.fetchall() ]
    con.close()
    return rows

# ---------------------- SHIMS для main.py -------------- #
# Контракт: from engine_paper import place_limit, place_tp, place_sl, cancel, positions, get_balance
# Эти функции маппятся на paper_trades.

def get_balance() -> float:
    con = _connect(DB_PATH)
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute("SELECT amount FROM balance WHERE id=1")
    row = cur.fetchone()
    con.close()
    return float(row[0]) if row else 0.0

def positions() -> List[Dict[str, Any]]:
    """Возвращает открытые позиции (open paper_trades)."""
    return get_open_trades(DB_PATH)

def place_limit(symbol: str, side: str, qty: Optional[float], price: float,
                tf: str = "paper", **kwargs) -> int:
    """
    Создать лимитную 'бумажную' позицию.
    SL/TP могут быть выставлены позже через place_sl/place_tp.
    Пока ставим stop=entry и tp1=tp2=tp3=entry, чтобы не закрывалось мгновенно.
    qty, если не задан, считается от USD_SIZE и LEVERAGE.
    """
    q = float(qty) if qty else _calc_qty(price)
    con = _connect(DB_PATH)
    _ensure_schema(con)
    opened = _now()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO paper_trades
        (symbol, tf, side, entry, stop, tp1, tp2, tp3, qty, status,
         opened_at, entered_at, last_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
    """, (symbol, tf, side, price, price, price, price, price, q, opened, opened, price))
    tid = cur.lastrowid
    con.commit()
    con.close()
    return tid

def place_sl(trade_id: int, sl_price: float, **kwargs) -> None:
    """Обновить стоп-лосс у позиции."""
    con = _connect(DB_PATH)
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute("UPDATE paper_trades SET stop=? WHERE id=? AND status='open'", (float(sl_price), int(trade_id)))
    con.commit()
    con.close()

def place_tp(trade_id: int, tp1: Optional[float] = None, tp2: Optional[float] = None,
             tp3: Optional[float] = None, tps: Optional[List[float]] = None, **kwargs) -> None:
    """
    Установить тейк-профиты. Можно передать tp1/tp2/tp3 или список tps.
    Пустые значения не перетирают текущие.
    """
    if tps and not (tp1 or tp2 or tp3):
        if len(tps) > 0: tp1 = tps[0]
        if len(tps) > 1: tp2 = tps[1]
        if len(tps) > 2: tp3 = tps[2]
    con = _connect(DB_PATH)
    _ensure_schema(con)
    cur = con.cursor()
    # читаем текущее
    cur.execute("SELECT tp1, tp2, tp3 FROM paper_trades WHERE id=? AND status='open'", (int(trade_id),))
    row = cur.fetchone()
    if not row:
        con.close()
        return
    v1, v2, v3 = row["tp1"], row["tp2"], row["tp3"]
    n1 = float(tp1) if tp1 is not None else v1
    n2 = float(tp2) if tp2 is not None else v2
    n3 = float(tp3) if tp3 is not None else v3
    cur.execute("UPDATE paper_trades SET tp1=?, tp2=?, tp3=? WHERE id=? AND status='open'", (n1, n2, n3, int(trade_id)))
    con.commit()
    con.close()

def cancel(trade_id: int, **kwargs) -> None:
    """Отменить/закрыть позицию без ПнЛ (бумажно)."""
    con = _connect(DB_PATH)
    _ensure_schema(con)
    cur = con.cursor()
    cur.execute("""
        UPDATE paper_trades
        SET status='cancel', closed_at=?, last_price=entry
        WHERE id=? AND status='open'
    """, (_now(), int(trade_id)))
    con.commit()
    con.close()
