#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, os, shutil, sys, time

DB_PATH = "bot.db"

# --- safety: stop if DB missing
if not os.path.exists(DB_PATH):
    print(f"DB not found: {DB_PATH}")
    sys.exit(1)

# --- backup
stamp = time.strftime("%Y%m%d_%H%M%S")
bak = f"{DB_PATH}.bak_levels_{stamp}"
shutil.copy2(DB_PATH, bak)
print(f"Backup: {bak}")

con = sqlite3.connect(DB_PATH)
con.isolation_level = None  # manual transaction
cur = con.cursor()

def cols_of(table: str):
    return [(r[1], r[2], r[4], r[3]) for r in cur.execute(f"PRAGMA table_info({table})")]
    # returns list of (name, type, dflt_value, notnull)

# --- ensure source table exists
try:
    cur.execute("SELECT 1 FROM levels LIMIT 1")
except sqlite3.Error as e:
    print("ERROR: table 'levels' not found or unreadable:", e)
    con.close()
    sys.exit(2)

src_cols = [c[0] for c in cols_of("levels")]

# --- desired schema (минимально необходимая контрактом main/strategy/charting)
DDL = """
CREATE TABLE IF NOT EXISTS levels_new (
    symbol       TEXT NOT NULL,
    tf           TEXT NOT NULL,
    base_ts      INTEGER NOT NULL DEFAULT 0,
    base_open    REAL    NOT NULL DEFAULT 0,
    base_high    REAL    NOT NULL DEFAULT 0,
    base_low     REAL    NOT NULL DEFAULT 0,
    base_close   REAL    NOT NULL DEFAULT 0,
    base_json    TEXT    NOT NULL DEFAULT '{}',
    levels_json  TEXT    NOT NULL DEFAULT '{}',
    PRIMARY KEY (symbol, tf)
);
"""

# Построим динамический SELECT c COALESCE() в зависимости от того, есть ли колонка
def sel_or_default(name: str, default_sql: str):
    return f"COALESCE({name}, {default_sql})" if name in src_cols else f"{default_sql}"

# В любых старых схемах ожидаем хотя бы symbol, tf; иначе миграция невозможна.
for req in ("symbol", "tf"):
    if req not in src_cols:
        print(f"ERROR: source table 'levels' missing required column: {req}")
        con.close()
        sys.exit(3)

select_sql = f"""
SELECT
    symbol                                         AS symbol,
    tf                                             AS tf,
    {sel_or_default("base_ts", "0")}               AS base_ts,
    {sel_or_default("base_open", "0")}             AS base_open,
    {sel_or_default("base_high", "0")}             AS base_high,
    {sel_or_default("base_low", "0")}              AS base_low,
    {sel_or_default("base_close", "0")}            AS base_close,
    {sel_or_default("base_json", "'{{}}'")}        AS base_json,
    {sel_or_default("levels_json", "'{{}}'")}      AS levels_json
FROM levels
"""

try:
    cur.execute("BEGIN IMMEDIATE")
    # создаём новую таблицу
    cur.executescript(DDL)
    # заполняем её данными из старой
    cur.execute(f"""
        INSERT OR REPLACE INTO levels_new
        (symbol, tf, base_ts, base_open, base_high, base_low, base_close, base_json, levels_json)
        {select_sql}
    """)
    # меняем местами
    cur.execute("DROP TABLE levels")
    cur.execute("ALTER TABLE levels_new RENAME TO levels")
    cur.execute("COMMIT")
    print("✅ Migration OK: table 'levels' rebuilt with defaults.")
except Exception as e:
    cur.execute("ROLLBACK")
    print("ERROR:", e)
    print("Restored from backup:", bak)
    con.close()
    sys.exit(4)

con.close()
