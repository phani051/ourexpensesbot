import sqlite3
import secrets
from config import DB_NAME


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ===================== GROUPS =====================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        invite_code TEXT UNIQUE,
        timezone TEXT DEFAULT 'Asia/Kolkata'
    )
    """)

    # Ensure columns exist (migration for older DBs)
    def add_column_if_missing(table, column, definition):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition};")

    add_column_if_missing("groups", "invite_code", "TEXT UNIQUE")
    add_column_if_missing("groups", "timezone", "TEXT DEFAULT 'Asia/Kolkata'")

    # ===================== USERS =====================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        group_id INTEGER
    )
    """)

    # ===================== EXPENSES =====================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        user TEXT,
        amount REAL,
        category TEXT,
        note TEXT,
        group_id INTEGER
    )
    """)

    # Ensure group_id exists
    add_column_if_missing("expenses", "group_id", "INTEGER")

    # ===================== INCOME =====================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        user TEXT,
        amount REAL,
        note TEXT,
        group_id INTEGER
    )
    """)

    # Ensure group_id exists
    add_column_if_missing("income", "group_id", "INTEGER")

    # ===================== BUDGETS =====================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        category TEXT,
        limit_amount REAL,
        group_id INTEGER,
        UNIQUE(category, group_id)
    )
    """)

    # ===================== ALERTS =====================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        group_id INTEGER,
        category TEXT,
        last_alert TEXT,
        UNIQUE(group_id, category)
    )
    """)

    # ===================== FIXES & MIGRATIONS =====================

    # Fix usernames
    cursor.execute("""
        UPDATE users
        SET username = 'Unknown'
        WHERE username IS NULL OR username = ''
    """)

    # Generate invite codes for groups missing one
    cursor.execute("SELECT id FROM groups WHERE invite_code IS NULL OR invite_code=''")
    groups_without_code = cursor.fetchall()
    for (group_id,) in groups_without_code:
        code = secrets.token_hex(4)  # 8-char code
        cursor.execute("UPDATE groups SET invite_code=? WHERE id=?", (code, group_id))

    conn.commit()
    conn.close()
