#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import json
from typing import Optional, Dict, Any, Tuple

DB_PATH = "bot.db"

# --------------------------------
# БАЗА
# --------------------------------
def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con

def _table_has_column(cur: sqlite3.Cursor, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

def db_init() -> None:
    """Минимальная инициализация — только kv, без трогания существующих таблиц."""
    con = db(); cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kv(
            k TEXT PRIMARY KEY,
            v TEXT
        )
    """)
    con.commit()
    con.close()

# --------------------------------
# KV (ТОЛЬКО k,v — без 'value')
# --------------------------------
def get_kv(key: str) -> Optional[str]:
    con = db(); cur = con.cursor()
    try:
        cur.execute("SELECT v FROM kv WHERE k = ?", (key,))
        row = cur.fetchone()
        return row["v"] if row else None
    finally:
        con.close()

def set_kv(key: str, val: str) -> None:
    con = db(); cur = con.cursor()
    try:
        cur.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, val))
        con.commit()
    finally:
        con.close()

# --------------------------------
# LEVELS (не меняю твою схему; работаю с тем, что уже есть)
# Ожидаемые поля (если есть): symbol, tf, base_ts, base_open, base_high, base_low, base_close, base_json, levels_json
# --------------------------------
def _select_levels_row(cur: sqlite3.Cursor, symbol: str, tf: str) -> Tuple[Optional[sqlite3.Row], Dict[str, bool]]:
    cur.execute("PRAGMA table_info(levels)")
    cols = {r[1]: True for r in cur.fetchall()}
    cur.execute("SELECT * FROM levels WHERE symbol=? AND tf=? LIMIT 1", (symbol, tf))
    row = cur.fetchone()
    return row, cols

def get_levels(symbol: str, tf: str) -> Optional[Dict[str, Any]]:
    con = db(); cur = con.cursor()
    try:
        row, cols = _select_levels_row(cur, symbol, tf)
        if not row:
            return None

        # base
        base: Dict[str, Any] = {}
        if cols.get("base_json") and row["base_json"]:
            try:
                base = json.loads(row["base_json"])
            except Exception:
                base = {}
        else:
            # собрать из base_* если есть
            for k in ("base_ts","base_open","base_high","base_low","base_close"):
                if cols.get(k):
                    base[k.replace("base_","")] = row[k]

        # levels
        levels: Dict[str, float] = {}
        if cols.get("levels_json") and row["levels_json"]:
            try:
                levels = json.loads(row["levels_json"])
            except Exception:
                levels = {}

        return {
            "symbol": row["symbol"],
            "tf": row["tf"],
            "base": base if base else None,
            "levels": levels if levels else None,
        }
    finally:
        con.close()

def set_levels(symbol: str, tf: str, base: Dict[str, Any], levels: Dict[str, float]) -> None:
    con = db(); cur = con.cursor()
    try:
        # какие колонки реально есть
        cur.execute("PRAGMA table_info(levels)")
        cols = {r[1]: True for r in cur.fetchall()}

        # готовим набор полей к UPSERT
        fields = ["symbol","tf"]
        params = [symbol, tf]

        if cols.get("base_ts"):
            fields.append("base_ts"); params.append(int(base.get("ts", 0)))
        if cols.get("base_open"):
            fields.append("base_open"); params.append(float(base.get("open", 0.0)))
        if cols.get("base_high"):
            fields.append("base_high"); params.append(float(base.get("high", 0.0)))
        if cols.get("base_low"):
            fields.append("base_low"); params.append(float(base.get("low", 0.0)))
        if cols.get("base_close"):
            fields.append("base_close"); params.append(float(base.get("close", 0.0)))
        if cols.get("base_json"):
            fields.append("base_json"); params.append(json.dumps(base, ensure_ascii=False))
        if cols.get("levels_json"):
            fields.append("levels_json"); params.append(json.dumps(levels, ensure_ascii=False))

        # upsert
        placeholders = ",".join(["?"] * len(params))
        cols_sql = ",".join(fields)
        updates_sql = ",".join([f"{f}=excluded.{f}" for f in fields if f not in ("symbol","tf")])

        cur.execute(f"""
            INSERT INTO levels ({cols_sql}) VALUES ({placeholders})
            ON CONFLICT(symbol, tf) DO UPDATE SET {updates_sql}
        """, params)
        con.commit()
    finally:
        con.close()
