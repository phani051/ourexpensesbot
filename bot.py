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

    # Create tables if not exist
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

    # Migration: add missing columns
    def add_column_if_missing(table, column, definition):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition};")
        except sqlite3.OperationalError:
            pass

    add_column_if_missing("expenses", "group_id", "INTEGER DEFAULT 1")
    add_column_if_missing("income", "group_id", "INTEGER DEFAULT 1")
    add_column_if_missing("budgets", "group_id", "INTEGER DEFAULT 1")

    # Migration: ensure UNIQUE constraint on budgets
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

    # Migration: Fix null usernames
    cursor.execute("""
        UPDATE users
        SET username = 'Unknown'
        WHERE username IS NULL OR username = ''
    """)

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
        BotCommand("setbudget", "Set category budget"),
        BotCommand("list", "List current month expenses"),
        BotCommand("categories", "Show categories & budgets"),
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
            "You already belong to a group. You cannot join or create another group."
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

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: Remove a user from the current group by username."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Only admin can remove users.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /removeuser <username>")
        return

    username = context.args[0]
    group_id = get_user_group_id(update.effective_user.id)

    if not group_id:
        await update.message.reply_text("Admin is not currently assigned to a group.")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # Verify user exists in group
    cursor.execute(
        "SELECT user_id FROM users WHERE username=? AND group_id=?",
        (username, group_id)
    )
    user_row = cursor.fetchone()

    if not user_row:
        await update.message.reply_text(f"User '{username}' not found in this group.")
        conn.close()
        return

    # Remove user
    cursor.execute("DELETE FROM users WHERE username=? AND group_id=?", (username, group_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"User '{username}' has been removed from the group.")

# ===================== EXPENSE COMMANDS =====================
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

    # Check budget
    cursor.execute("SELECT limit_amount FROM budgets WHERE category=? AND group_id=?", (category, group_id))
    budget = cursor.fetchone()

    conn.commit()
    conn.close()

    msg = f"Added expense: {amount} in {category}"
    if budget:
        limit = budget[0]
        cursor_sum = sqlite3.connect("expenses.db").cursor()
        cursor_sum.execute("SELECT SUM(amount) FROM expenses WHERE category=? AND group_id=?", (category, group_id))
        total = cursor_sum.fetchone()[0] or 0
        cursor_sum.connection.close()

        if total > limit:
            msg += f"\n⚠️ Over budget! ({total}/{limit})"
        elif total > 0.8 * limit:
            msg += f"\n⚠️ Near budget limit ({total}/{limit})"

    await update.message.reply_text(msg)

# ===================== BUDGET COMMAND =====================
@require_group
async def set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setbudget <category> <limit>")
        return

    category = context.args[0]
    try:
        limit = float(context.args[1])
    except:
        await update.message.reply_text("Limit must be a number.")
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

    await update.message.reply_text(f"Budget for '{category}' set to {limit}")

# ===================== CATEGORY REPORT =====================
@require_group
async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_id = get_user_group_id(update.effective_user.id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("SELECT category, SUM(amount) FROM expenses WHERE group_id=? GROUP BY category", (group_id,))
    spent = dict(cursor.fetchall())

    cursor.execute("SELECT category, limit_amount FROM budgets WHERE group_id=?", (group_id,))
    budgets = dict(cursor.fetchall())

    conn.close()

    if not spent and not budgets:
        await update.message.reply_text("No categories or budgets set.")
        return

    over_budget = []
    message = "Category Spendings:\n"
    for category in set(list(spent.keys()) + list(budgets.keys())):
        total = spent.get(category, 0)
        limit = budgets.get(category)
        if limit:
            if total > limit:
                status = "🔴 Over budget"
                over_budget.append(category)
            elif total > 0.8 * limit:
                status = "🟡 Near limit"
            else:
                status = "🟢 OK"
            message += f"{category}: {total}/{limit} {status}\n"
        else:
            message += f"{category}: {total}\n"

    if over_budget:
        message = "⚠️ Warning: Budgets exceeded for: " + ", ".join(over_budget) + "\n\n" + message

    await update.message.reply_text(message)

# ===================== INCOME COMMAND =====================
@require_group
async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])
        note = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    except:
        await update.message.reply_text("Usage: /income <amount> <note>")
        return

    group_id = get_user_group_id(update.effective_user.id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO income (timestamp, user, amount, note, group_id) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), update.effective_user.first_name, amount, note, group_id)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Income added: {amount}")

# ===================== LIST EXPENSES =====================
@require_group
async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_id = get_user_group_id(update.effective_user.id)
    month = get_current_month()

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # Fetch expenses for the month
    cursor.execute("""
        SELECT date(timestamp), amount, category, note
        FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ? AND group_id = ?
        ORDER BY timestamp ASC
    """, (month, group_id))
    rows = cursor.fetchall()

    # Fetch budgets
    cursor.execute("SELECT category, limit_amount FROM budgets WHERE group_id=?", (group_id,))
    budgets = dict(cursor.fetchall())

    # Fetch income total
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM income
        WHERE strftime('%Y-%m', timestamp) = ? AND group_id = ?
    """, (month, group_id))
    total_income = cursor.fetchone()[0]

    conn.close()

    # Calculate totals per category and total expenses
    totals = {}
    total_expenses = 0
    for _, amount, category, _ in rows:
        totals[category] = totals.get(category, 0) + amount
        total_expenses += amount

    balance = total_income - total_expenses

    # Prepare message
    if not rows:
        await update.message.reply_text(
            f"No expenses this month.\n\n"
            f"Total Income: {total_income}\n"
            f"Total Expenses: {total_expenses}\n"
            f"Balance: {balance}"
        )
        return

    message = f"Expenses for {month}:\n"
    for row in rows:
        message += f"{row[0]}: {row[1]} ({row[2]}) - {row[3]}\n"

    message += "\n--- Totals vs Budget ---\n"
    for cat, total in totals.items():
        limit = budgets.get(cat)
        if limit:
            status = "🔴 Over" if total > limit else ("🟡 Near" if total > 0.8 * limit else "🟢 OK")
            message += f"{cat}: {total}/{limit} {status}\n"
        else:
            message += f"{cat}: {total}\n"

    message += "\n--- Summary ---\n"
    message += f"Total Income: {total_income}\n"
    message += f"Total Expenses: {total_expenses}\n"
    message += f"Balance: {balance}\n"

    await update.message.reply_text(message)

# ===================== RESET COMMAND =====================
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
        "/setbudget <category> <limit> - Set category budget\n"
        "/list - Show monthly expenses\n"
        "/categories - Show category spendings\n"
        "/reset - Reset group data (confirmation required)\n"
        "/income <amount> <note> - Add income\n"
        "/listusers - Admin: list users in current group\n"
        "/removeuser <username> - Admin: remove user from group\n"
        "/listgroups - Admin: list all groups\n"
        "/switchgroup <group_name> - Admin: switch active group\n"
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
    app.add_handler(CommandHandler("removeuser", remove_user))

    # Expense handlers
    app.add_handler(CommandHandler("add", add_expense))
    app.add_handler(CommandHandler("list", list_expenses))
    app.add_handler(CommandHandler("categories", list_categories))
    app.add_handler(CommandHandler("setbudget", set_budget))
    app.add_handler(CommandHandler("income", add_income))

    # Reset handlers
    app.add_handler(CommandHandler("reset", reset_group))
    app.add_handler(CommandHandler("confirmreset", confirm_reset))

    # Others
    app.add_handler(CommandHandler("help", help_command))

    app.run_polling()

if __name__ == "__main__":
    main()
