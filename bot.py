import sqlite3
import pandas as pd
from io import BytesIO
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler
)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, time, timedelta

# ===================== CONFIG =====================
BOT_TOKEN = "7570600838:AAHFsLEK-BDTaBHaCwZyscHbOAdXTWXrT-4"
AUTHORIZED_USERS = [7414452859, 8128152854]   # Replace with your Telegram user IDs

# ===================== DB INIT =====================
def init_db():
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        user TEXT,
        amount REAL,
        category TEXT,
        note TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        user TEXT,
        amount REAL,
        note TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        category TEXT PRIMARY KEY,
        limit_amount REAL
    )
    """)

    conn.commit()
    conn.close()

# ===================== UTILS =====================
def is_authorized(user_id):
    return user_id in AUTHORIZED_USERS

def get_current_month():
    return datetime.now().strftime("%Y-%m")

def get_last_month():
    first_day_this_month = datetime.now().replace(day=1)
    last_month_date = first_day_this_month - timedelta(days=1)
    return last_month_date.strftime("%Y-%m")

# ===================== MENU BUTTON SETUP =====================
async def set_bot_commands(app):
    commands = [
        BotCommand("add", "Add expense: /add <amount> <category> <note>"),
        BotCommand("income", "Add income: /income <amount> <note>"),
        BotCommand("list", "Show expenses this month"),
        BotCommand("categories", "Show categories & budgets"),
        BotCommand("summary", "Monthly summary with charts"),
        BotCommand("setbudget", "Set budget: /setbudget <category> <amount>"),
        BotCommand("export", "Export all data to Excel"),
        BotCommand("lastmonth", "Export last month's data"),
        BotCommand("currentmonth", "Export current month's data"),
        BotCommand("reset", "Reset all data (confirmation)"),
        BotCommand("help", "Show help")
    ]
    await app.bot.set_my_commands(commands)

# ===================== COMMAND HANDLERS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return
    await update.message.reply_text("Welcome to Expense Tracker Bot!\nUse /help to see commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Available Commands:
/add <amount> <category> <note> - Add expense
/income <amount> <note> - Add income
/list - List current month expenses
/categories - Show categories and budgets
/summary - Show summary with chart
/setbudget <category> <amount> - Set category budget
/export - Export full data to Excel
/lastmonth - Export last month’s data
/currentmonth - Export current month’s data
/reset - Reset all data (confirmation)
/help - Show this help
"""
    await update.message.reply_text(help_text)

# Add Expense
async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return
    try:
        amount = float(context.args[0])
        category = context.args[1]
        note = " ".join(context.args[2:]) if len(context.args) > 2 else ""
    except:
        await update.message.reply_text("Usage: /add <amount> <category> <note>")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (timestamp, user, amount, category, note) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), update.effective_user.first_name, amount, category, note)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Added expense: {amount} in {category}")

# Add Income
async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return
    try:
        amount = float(context.args[0])
        note = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    except:
        await update.message.reply_text("Usage: /income <amount> <note>")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO income (timestamp, user, amount, note) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), update.effective_user.first_name, amount, note)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Added income: {amount}")

# List Current Month Expenses
async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return

    month = get_current_month()
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date(timestamp), amount, category, note
        FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ?
        ORDER BY timestamp ASC
    """, (month,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No expenses this month.")
        return

    message = "Expenses this month:\n"
    for row in rows:
        message += f"{row[0]}: {row[1]} ({row[2]}) - {row[3]}\n"

    await update.message.reply_text(message)

# Categories + Budget
async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("SELECT category, SUM(amount) FROM expenses GROUP BY category")
    spent = cursor.fetchall()

    cursor.execute("SELECT category, limit_amount FROM budgets")
    budgets = dict(cursor.fetchall())

    conn.close()

    message = "Category Spendings:\n"
    for cat, total in spent:
        budget_text = f"/ {budgets[cat]}" if cat in budgets else ""
        message += f"{cat}: {total}{budget_text}\n"

    await update.message.reply_text(message)

# Set Budget
async def set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setbudget <category> <amount>")
        return
    category = context.args[0]
    try:
        amount = float(context.args[1])
    except:
        await update.message.reply_text("Amount must be a number.")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO budgets (category, limit_amount) VALUES (?, ?)", (category, amount))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Budget for {category} set to {amount}")

# Summary with Pie Chart
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return

    month = get_current_month()
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ?
        GROUP BY category
    """, (month,))
    data = cursor.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("No data for summary.")
        return

    categories = [row[0] for row in data]
    amounts = [row[1] for row in data]

    plt.figure(figsize=(5, 5))
    plt.pie(amounts, labels=categories, autopct='%1.1f%%')
    plt.title(f"Spending Summary - {month}")
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()

    await update.message.reply_photo(photo=buffer)

# Export Full Data
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return

    conn = sqlite3.connect("expenses.db")
    expenses = pd.read_sql_query("SELECT * FROM expenses", conn)
    income = pd.read_sql_query("SELECT * FROM income", conn)
    conn.close()

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        expenses.to_excel(writer, sheet_name="Expenses", index=False)
        income.to_excel(writer, sheet_name="Income", index=False)
    buffer.seek(0)

    await update.message.reply_document(
        document=buffer,
        filename="expenses_full.xlsx",
        caption="Full Export"
    )

# Reset with confirmation
async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return

    keyboard = [
        [
            InlineKeyboardButton("Confirm Reset", callback_data="confirm_reset"),
            InlineKeyboardButton("Cancel", callback_data="cancel_reset")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Are you sure you want to reset ALL data?", reply_markup=reply_markup)

async def reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_reset":
        conn = sqlite3.connect("expenses.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses")
        cursor.execute("DELETE FROM income")
        cursor.execute("DELETE FROM budgets")
        conn.commit()
        conn.close()

        await query.edit_message_text("✅ All data has been reset.")
    else:
        await query.edit_message_text("❌ Reset cancelled.")

# ===================== DAILY BUDGET ALERT =====================
async def daily_budget_alert(context: ContextTypes.DEFAULT_TYPE):
    month = get_current_month()
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("SELECT category, SUM(amount) FROM expenses WHERE strftime('%Y-%m', timestamp)=? GROUP BY category", (month,))
    spent = dict(cursor.fetchall())

    cursor.execute("SELECT category, limit_amount FROM budgets")
    budgets = dict(cursor.fetchall())

    conn.close()

    alerts = []
    for cat, limit in budgets.items():
        if cat in spent and spent[cat] >= limit:
            alerts.append(f"⚠️ {cat} exceeded budget! ({spent[cat]}/{limit})")
        elif cat in spent and spent[cat] >= 0.9 * limit:
            alerts.append(f"⚠️ {cat} nearing budget! ({spent[cat]}/{limit})")

    if alerts:
        message = "\n".join(alerts)
        for user_id in AUTHORIZED_USERS:
            await context.bot.send_message(chat_id=user_id, text=message)

# ------------------ MONTHLY AUTO EXPORT + RESET ------------------
async def monthly_export_and_reset_prompt(context: ContextTypes.DEFAULT_TYPE):
    last_month = get_last_month()

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date(timestamp), user, amount, category, note
        FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ?
        ORDER BY timestamp ASC
    """, (last_month,))
    expenses = cursor.fetchall()

    cursor.execute("""
        SELECT date(timestamp), user, amount, note
        FROM income
        WHERE strftime('%Y-%m', timestamp) = ?
        ORDER BY timestamp ASC
    """, (last_month,))
    incomes = cursor.fetchall()
    conn.close()

    if not expenses and not incomes:
        return

    expense_df = pd.DataFrame(expenses, columns=["Date", "User", "Amount", "Category", "Note"])
    income_df = pd.DataFrame(incomes, columns=["Date", "User", "Amount", "Note"])

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        expense_df.to_excel(writer, sheet_name="Expenses", index=False)
        income_df.to_excel(writer, sheet_name="Income", index=False)
    excel_buffer.seek(0)

    for user_id in AUTHORIZED_USERS:
        await context.bot.send_document(
            chat_id=user_id,
            document=excel_buffer,
            filename=f"expenses_{last_month}.xlsx",
            caption=f"📊 Monthly Report for {last_month}"
        )

        keyboard = [
            [
                InlineKeyboardButton("Confirm Reset Last Month", callback_data=f"monthly_reset_{last_month}"),
                InlineKeyboardButton("Cancel", callback_data="cancel_monthly_reset")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"Do you want to reset data for **{last_month}**?",
            reply_markup=reply_markup
        )

async def monthly_reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("monthly_reset_"):
        last_month = query.data.replace("monthly_reset_", "")
        conn = sqlite3.connect("expenses.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses WHERE strftime('%Y-%m', timestamp) = ?", (last_month,))
        cursor.execute("DELETE FROM income WHERE strftime('%Y-%m', timestamp) = ?", (last_month,))
        conn.commit()
        conn.close()

        await query.edit_message_text(f"✅ Data for {last_month} has been reset.")
    else:
        await query.edit_message_text("❌ Monthly reset cancelled.")

# ----------------- MANUAL EXPORT COMMANDS -----------------
async def export_last_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return

    last_month = get_last_month()
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT date(timestamp), user, amount, category, note
        FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ?
        ORDER BY timestamp ASC
    """, (last_month,))
    expenses = cursor.fetchall()

    cursor.execute("""
        SELECT date(timestamp), user, amount, note
        FROM income
        WHERE strftime('%Y-%m', timestamp) = ?
        ORDER BY timestamp ASC
    """, (last_month,))
    incomes = cursor.fetchall()

    conn.close()

    if not expenses and not incomes:
        await update.message.reply_text(f"No data found for {last_month}.")
        return

    expense_df = pd.DataFrame(expenses, columns=["Date", "User", "Amount", "Category", "Note"])
    income_df = pd.DataFrame(incomes, columns=["Date", "User", "Amount", "Note"])

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        expense_df.to_excel(writer, sheet_name="Expenses", index=False)
        income_df.to_excel(writer, sheet_name="Income", index=False)
    excel_buffer.seek(0)

    await update.message.reply_document(
        document=excel_buffer,
        filename=f"expenses_{last_month}.xlsx",
        caption=f"Manual Export: {last_month}"
    )

async def export_current_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access Denied.")
        return

    current_month = get_current_month()
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT date(timestamp), user, amount, category, note
        FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ?
        ORDER BY timestamp ASC
    """, (current_month,))
    expenses = cursor.fetchall()

    cursor.execute("""
        SELECT date(timestamp), user, amount, note
        FROM income
        WHERE strftime('%Y-%m', timestamp) = ?
        ORDER BY timestamp ASC
    """, (current_month,))
    incomes = cursor.fetchall()

    conn.close()

    if not expenses and not incomes:
        await update.message.reply_text(f"No data found for {current_month}.")
        return

    expense_df = pd.DataFrame(expenses, columns=["Date", "User", "Amount", "Category", "Note"])
    income_df = pd.DataFrame(incomes, columns=["Date", "User", "Amount", "Note"])

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        expense_df.to_excel(writer, sheet_name="Expenses", index=False)
        income_df.to_excel(writer, sheet_name="Income", index=False)
    excel_buffer.seek(0)

    await update.message.reply_document(
        document=excel_buffer,
        filename=f"expenses_{current_month}.xlsx",
        caption=f"Manual Export: {current_month}"
    )

# ===================== MAIN =====================
async def post_init(application):
    await set_bot_commands(application)

def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Register all command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_expense))
    app.add_handler(CommandHandler("income", add_income))
    app.add_handler(CommandHandler("list", list_expenses))
    app.add_handler(CommandHandler("categories", list_categories))
    app.add_handler(CommandHandler("setbudget", set_budget))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("export", export_data))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("lastmonth", export_last_month))
    app.add_handler(CommandHandler("currentmonth", export_current_month))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(reset_callback, pattern="^confirm_reset|cancel_reset$"))
    app.add_handler(CallbackQueryHandler(monthly_reset_callback, pattern="^monthly_reset_|cancel_monthly_reset$"))

    # Scheduled jobs
    app.job_queue.run_daily(daily_budget_alert, time=time(hour=9, minute=0))
    app.job_queue.run_monthly(
        monthly_export_and_reset_prompt,
        when=time(hour=0, minute=5),
        day=1
    )

    app.run_polling()

if __name__ == "__main__":
    main()
