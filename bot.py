import sqlite3
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)
from datetime import datetime

# ===================== CONFIG =====================
BOT_TOKEN = "7570600838:AAHFsLEK-BDTaBHaCwZyscHbOAdXTWXrT-4"
ADMIN_ID = 7414452859  # Replace with your Telegram user ID

# ===================== DB INIT (with migration) =====================
def init_db():
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # Expenses table
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

    # Income table
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

    # Groups table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    """)

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        group_id INTEGER
    )
    """)

    # Budgets table (with UNIQUE constraint)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        category TEXT,
        limit_amount REAL,
        group_id INTEGER,
        UNIQUE(category, group_id)
    )
    """)

    # Ensure unique constraint exists
    cursor.execute("PRAGMA index_list(budgets)")
    indexes = cursor.fetchall()
    has_unique = any(idx[2] == 1 for idx in indexes)

    if not has_unique:
        cursor.execute("SELECT category, limit_amount, group_id FROM budgets")
        old_data = cursor.fetchall()

        cursor.execute("DROP TABLE budgets")
        cursor.execute("""
        CREATE TABLE budgets (
            category TEXT,
            limit_amount REAL,
            group_id INTEGER,
            UNIQUE(category, group_id)
        )
        """)

        if old_data:
            cursor.executemany(
                "INSERT OR IGNORE INTO budgets (category, limit_amount, group_id) VALUES (?, ?, ?)",
                old_data
            )

    conn.commit()
    conn.close()

# ===================== UTILS =====================
def get_user_group_id(user_id):
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT group_id FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def require_group(func):
    """Decorator to ensure user has joined a group."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        group_id = get_user_group_id(update.effective_user.id)
        if not group_id:
            await update.message.reply_text(
                "You must first create or join a group using:\n/startgroup <group_name>"
            )
            return
        return await func(update, context)
    return wrapper

def get_current_month():
    return datetime.now().strftime("%Y-%m")

# ===================== MENU BUTTON =====================
async def set_bot_commands(app):
    commands = [
        BotCommand("startgroup", "Create or join a group"),
        BotCommand("mygroup", "Show your current group"),
        BotCommand("add", "Add expense"),
        BotCommand("list", "List current month expenses"),
        BotCommand("categories", "Show categories & budgets"),
        BotCommand("setbudget", "Set budget for category"),
        BotCommand("switchgroup", "Admin: switch group"),
        BotCommand("listusers", "Admin: list users in current group"),
        BotCommand("listgroups", "Admin: list all groups"),
        BotCommand("reset", "Reset group data"),
        BotCommand("help", "Show help")
    ]
    await app.bot.set_my_commands(commands)

# ===================== GROUP COMMANDS =====================
async def startgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    existing_group_id = get_user_group_id(user_id)
    if existing_group_id and user_id != ADMIN_ID:
        await update.message.reply_text(
            "You already belong to a group. Cannot join another group."
        )
        return

    if not context.args:
        await update.message.reply_text("Usage: /startgroup <group_name>")
        return

    group_name = context.args[0]

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM groups WHERE name=?", (group_name,))
    existing = cursor.fetchone()

    if existing:
        group_id = existing[0]
    else:
        cursor.execute("INSERT INTO groups (name) VALUES (?)", (group_name,))
        group_id = cursor.lastrowid

    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, group_id)
        VALUES (?, ?, ?)
    """, (user_id, update.effective_user.username, group_id))

    conn.commit()
    conn.close()

    await update.message.reply_text(f"Joined group: {group_name}")

async def mygroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_id = get_user_group_id(update.effective_user.id)
    if not group_id:
        await update.message.reply_text("You are not part of any group.")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM groups WHERE id=?", (group_id,))
    name = cursor.fetchone()[0]
    conn.close()

    await update.message.reply_text(f"Your current group: {name}")

# ===================== ADMIN COMMANDS =====================
async def switchgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Only admin can switch groups.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /switchgroup <group_name>")
        return

    group_name = context.args[0]

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM groups WHERE name=?", (group_name,))
    existing = cursor.fetchone()

    if not existing:
        await update.message.reply_text("Group not found.")
        conn.close()
        return

    group_id = existing[0]
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, group_id)
        VALUES (?, ?, ?)
    """, (update.effective_user.id, update.effective_user.username, group_id))

    conn.commit()
    conn.close()

    await update.message.reply_text(f"Admin switched to group: {group_name}")

async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Only admin can view users.")
        return

    group_id = get_user_group_id(update.effective_user.id)
    if not group_id:
        await update.message.reply_text("Admin is not in any group currently.")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE group_id=?", (group_id,))
    users = cursor.fetchall()
    conn.close()

    if not users:
        await update.message.reply_text("No users in this group.")
        return

    message = "Users in this group:\n"
    for (username,) in users:
        message += f"- {username}\n"

    await update.message.reply_text(message)

async def listgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Only admin can view all groups.")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM groups")
    groups = cursor.fetchall()
    conn.close()

    if not groups:
        await update.message.reply_text("No groups found.")
        return

    message = "Groups available:\n"
    for group_id, name in groups:
        message += f"{group_id} - {name}\n"

    await update.message.reply_text(message)

# ===================== BUDGET COMMAND =====================
@require_group
async def set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setbudget <category> <amount>")
        return

    category = context.args[0]
    try:
        limit = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Amount must be a number.")
        return

    group_id = get_user_group_id(update.effective_user.id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO budgets (category, limit_amount, group_id)
        VALUES (?, ?, ?)
        ON CONFLICT(category, group_id) DO UPDATE SET limit_amount=excluded.limit_amount
    """, (category, limit, group_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Budget set for {category}: {limit}")

# ===================== ADD EXPENSE (with budget alert) =====================
@require_group
async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])
        category = context.args[1]
        note = " ".join(context.args[2:]) if len(context.args) > 2 else ""
    except:
        await update.message.reply_text("Usage: /add <amount> <category> <note>")
        return

    group_id = get_user_group_id(update.effective_user.id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (timestamp, user, amount, category, note, group_id) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), update.effective_user.first_name, amount, category, note, group_id)
    )

    # Check budget exceed
    cursor.execute("""
        SELECT SUM(amount) FROM expenses
        WHERE category=? AND group_id=?
    """, (category, group_id))
    total_spent = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT limit_amount FROM budgets
        WHERE category=? AND group_id=?
    """, (category, group_id))
    budget = cursor.fetchone()

    conn.commit()
    conn.close()

    if budget and total_spent > budget[0]:
        await update.message.reply_text(f"⚠️ Alert: Budget exceeded for {category}! Spent {total_spent}/{budget[0]}")

    await update.message.reply_text(f"Added expense: {amount} in {category}")

# ===================== LIST CATEGORIES =====================
@require_group
async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_id = get_user_group_id(update.effective_user.id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT category, SUM(amount) FROM expenses
        WHERE group_id=? GROUP BY category
    """, (group_id,))
    spent = cursor.fetchall()

    cursor.execute("SELECT category, limit_amount FROM budgets WHERE group_id=?", (group_id,))
    budgets = dict(cursor.fetchall())

    conn.close()

    if not spent and not budgets:
        await update.message.reply_text("No expenses or budgets set yet.")
        return

    message = "Category Spendings:\n"
    for cat, total in spent:
        limit = budgets.get(cat)
        if limit:
            message += f"{cat}: {total}/{limit}\n"
        else:
            message += f"{cat}: {total}\n"

    for cat, limit in budgets.items():
        if cat not in [c for c, _ in spent]:
            message += f"{cat}: 0/{limit}\n"

    await update.message.reply_text(message)

# ===================== LIST EXPENSES =====================
@require_group
async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_id = get_user_group_id(update.effective_user.id)
    month = get_current_month()

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date(timestamp), amount, category, note
        FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ? AND group_id = ?
        ORDER BY timestamp ASC
    """, (month, group_id))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No expenses this month.")
        return

    message = "Expenses this month:\n"
    for row in rows:
        message += f"{row[0]}: {row[1]} ({row[2]}) - {row[3]}\n"

    await update.message.reply_text(message)

# ===================== RESET =====================
@require_group
async def reset_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reset_pending'] = True
    await update.message.reply_text(
        "⚠️ This will permanently delete all expenses, income, and budgets for your group.\n"
        "Type /confirmreset within 30 seconds to proceed."
    )

@require_group
async def confirm_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('reset_pending'):
        await update.message.reply_text("No reset operation pending.")
        return

    group_id = get_user_group_id(update.effective_user.id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE group_id=?", (group_id,))
    cursor.execute("DELETE FROM income WHERE group_id=?", (group_id,))
    cursor.execute("DELETE FROM budgets WHERE group_id=?", (group_id,))
    conn.commit()
    conn.close()

    context.user_data['reset_pending'] = False
    await update.message.reply_text("Group data has been completely reset.")

# ===================== HELP =====================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/startgroup <name> - Create or join group\n"
        "/mygroup - Show current group\n"
        "/add <amount> <category> <note> - Add expense\n"
        "/list - Show monthly expenses\n"
        "/categories - Show category spendings\n"
        "/setbudget <category> <amount> - Set budget for category\n"
        "/switchgroup <name> - Admin: switch group\n"
        "/listusers - Admin: list users in current group\n"
        "/listgroups - Admin: list all groups\n"
        "/reset - Reset group data\n"
    )

# ===================== MAIN =====================
async def post_init(application):
    await set_bot_commands(application)

def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Group handlers
    app.add_handler(CommandHandler("startgroup", startgroup))
    app.add_handler(CommandHandler("mygroup", mygroup))

    # Admin handlers
    app.add_handler(CommandHandler("switchgroup", switchgroup))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(CommandHandler("listgroups", listgroups))

    # Budget/Expense handlers
    app.add_handler(CommandHandler("setbudget", set_budget))
    app.add_handler(CommandHandler("add", add_expense))
    app.add_handler(CommandHandler("list", list_expenses))
    app.add_handler(CommandHandler("categories", list_categories))

    # Reset handlers
    app.add_handler(CommandHandler("reset", reset_group))
    app.add_handler(CommandHandler("confirmreset", confirm_reset))

    # Help
    app.add_handler(CommandHandler("help", help_command))

    app.run_polling()

if __name__ == "__main__":
    main()
