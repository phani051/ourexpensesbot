# db.py
import sqlite3

from config import DB_NAME

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create tables
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        category TEXT,
        limit_amount REAL,
        group_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        group_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        group_id INTEGER,
        category TEXT,
        last_alert TEXT,
        UNIQUE(group_id, category)
    )
    """)

    # Migration helper
    def add_column_if_missing(table, column, definition):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition};")
        except sqlite3.OperationalError:
            pass

    add_column_if_missing("expenses", "group_id", "INTEGER DEFAULT 1")
    add_column_if_missing("income", "group_id", "INTEGER DEFAULT 1")
    add_column_if_missing("budgets", "group_id", "INTEGER DEFAULT 1")
    add_column_if_missing("groups", "timezone", "TEXT")

    # Ensure budgets unique
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets_new (
            category TEXT,
            limit_amount REAL,
            group_id INTEGER,
            UNIQUE(category, group_id)
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO budgets_new (category, limit_amount, group_id)
        SELECT category, limit_amount, group_id FROM budgets
    """)
    cursor.execute("DROP TABLE budgets")
    cursor.execute("ALTER TABLE budgets_new RENAME TO budgets")

    # Fix null usernames
    cursor.execute("""
        UPDATE users
        SET username = 'Unknown'
        WHERE username IS NULL OR username = ''
    """)
    # Migration: add timezone column to groups
    try:
        cursor.execute("ALTER TABLE groups ADD COLUMN timezone TEXT DEFAULT 'Asia/Kolkata'")
    except sqlite3.OperationalError:
        pass
    

    conn.commit()
    conn.close()
