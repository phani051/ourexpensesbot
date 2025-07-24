# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import sqlite3
import pandas as pd
import os

from config import DB_NAME
from utils import get_current_month


async def auto_export_last_month(bot):
    """Exports last month's data for all groups and sends Excel to group chat IDs"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM groups")
    groups = cursor.fetchall()
    conn.close()

    last_month = (datetime.now().replace(day=1) - pd.DateOffset(months=1)).strftime("%Y-%m")

    for (group_id,) in groups:
        # Export for this group
        conn = sqlite3.connect(DB_NAME)

        expenses_df = pd.read_sql_query(f"""
            SELECT timestamp, user, amount, category, note
            FROM expenses
            WHERE group_id = {group_id} AND strftime('%Y-%m', timestamp) = '{last_month}'
            ORDER BY timestamp ASC
        """, conn)

        income_df = pd.read_sql_query(f"""
            SELECT timestamp, user, amount, note
            FROM income
            WHERE group_id = {group_id} AND strftime('%Y-%m', timestamp) = '{last_month}'
            ORDER BY timestamp ASC
        """, conn)

        conn.close()

        if expenses_df.empty and income_df.empty:
            continue

        filename = f"export_{last_month}_group{group_id}.xlsx"
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            expenses_df.to_excel(writer, index=False, sheet_name="Expenses")
            income_df.to_excel(writer, index=False, sheet_name="Income")

        try:
            await bot.send_document(chat_id=group_id, document=open(filename, "rb"), filename=filename)
        finally:
            os.remove(filename)


def start_scheduler(bot):
    scheduler = AsyncIOScheduler()

    async def job():
        # Run daily, but only execute on 1st of month
        if datetime.now().day == 1:
            await auto_export_last_month(bot)

    scheduler.add_job(job, "interval", days=1)
    scheduler.start()
    return scheduler
