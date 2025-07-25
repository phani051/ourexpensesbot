# utils.py
import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from functools import wraps
#from dotenv import load_dotenv
import pytz
import os

from config import DB_NAME
from config import ADMIN_ID

def require_admin(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        return await func(update, context)
    return wrapper


def get_user_group_id(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT group_id FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_group_timezone(group_id):
    """
    Fetch timezone for a group from DB. Default to Asia/Kolkata if not set.
    """
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT timezone FROM groups WHERE id=?", (group_id,))
    row = cursor.fetchone()
    conn.close()

    # Default timezone is Asia/Kolkata
    tz_name = row[0] if row and row[0] else "Asia/Kolkata"
    return pytz.timezone(tz_name)

def get_current_time_for_group(group_id):
    """
    Get current timestamp in the group's timezone (default Asia/Kolkata).
    """
    tz = get_group_timezone(group_id)
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def require_group(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        group_id = get_user_group_id(update.effective_user.id)
        if not group_id:
            await update.message.reply_text(
                "You must first create or join a group using:\n/startgroup <group_name>"
            )
            return
        return await func(update, context)
    return wrapper


def get_current_month(group_id=None):
    """Return YYYY-MM of current time in group's timezone (default Asia/Kolkata)."""
    tz = pytz.timezone(get_group_timezone(group_id)) if group_id else pytz.timezone("Asia/Kolkata")
    return datetime.now(tz).strftime("%Y-%m")


def should_send_alert(group_id, category):
    """Check if 24 hours passed since last alert for this category/group."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT last_alert FROM alerts WHERE group_id=? AND category=?",
        (group_id, category)
    )
    row = cursor.fetchone()

    now = datetime.now()
    if row:
        last_alert = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        if now - last_alert < timedelta(hours=24):
            conn.close()
            return False  # Don't send again

    # Insert or update alert timestamp
    cursor.execute("""
        INSERT INTO alerts (group_id, category, last_alert)
        VALUES (?, ?, ?)
        ON CONFLICT(group_id, category) DO UPDATE SET last_alert=excluded.last_alert
    """, (group_id, category, now.strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()
    return True
