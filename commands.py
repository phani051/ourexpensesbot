import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from utils import get_user_group_id, require_group

# ===================== GROUP COMMANDS =====================

async def startgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create or join a group."""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    existing_group_id = get_user_group_id(user_id)
    if existing_group_id:
        await update.message.reply_text("⚠️ You are already part of a group. Leave it before joining another.")
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

    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, username, group_id) VALUES (?, ?, ?)",
        (user_id, username, group_id),
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(f"🎉 You have joined group: *{group_name}*", parse_mode="Markdown")


async def mygroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current group of user."""
    group_id = get_user_group_id(update.effective_user.id)
    if not group_id:
        await update.message.reply_text("❌ You are not part of any group.")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM groups WHERE id=?", (group_id,))
    name = cursor.fetchone()[0]
    conn.close()

    await update.message.reply_text(f"👥 Your current group: *{name}*", parse_mode="Markdown")


async def listgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available groups."""
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM groups")
    groups = cursor.fetchall()
    conn.close()

    if not groups:
        await update.message.reply_text("📭 No groups available.")
        return

    text = "📋 *Available Groups:*\n\n"
    for g in groups:
        text += f"- {g[0]}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def switchgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch user to another group."""
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Usage: /switchgroup <group_name>")
        return

    group_name = context.args[0]

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM groups WHERE name=?", (group_name,))
    group = cursor.fetchone()

    if not group:
        await update.message.reply_text("❌ Group not found.")
        conn.close()
        return

    group_id = group[0]

    cursor.execute(
        "UPDATE users SET group_id=? WHERE user_id=?",
        (group_id, user_id),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"🔄 Switched to group: *{group_name}*", parse_mode="Markdown")


# ===================== USER MANAGEMENT =====================

async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List users in current group."""
    group_id = get_user_group_id(update.effective_user.id)
    if not group_id:
        await update.message.reply_text("❌ You are not part of any group.")
        return

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE group_id=?", (group_id,))
    users = cursor.fetchall()
    conn.close()

    if not users:
        await update.message.reply_text("📭 No users in this group.")
        return

    text = "👥 *Users in this group:*\n\n"
    for u in users:
        text += f"- {u[0]}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a user by username from group."""
    if not context.args:
        await update.message.reply_text("Usage: /removeuser <username>")
        return

    username = context.args[0]
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"🗑️ Removed user: *{username}*", parse_mode="Markdown")


# ===================== EXPENSE & INCOME =====================

@require_group
async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new expense."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /add <amount> <category> [note]")
        return

    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount.")
        return

    category = context.args[1]
    note = " ".join(context.args[2:]) if len(context.args) > 2 else ""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    group_id = get_user_group_id(user_id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO expenses (timestamp, user, amount, category, note, group_id) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, amount, category, note, group_id),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"💸 Expense added: *{amount}* in *{category}*", parse_mode="Markdown")


@require_group
async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add income to the group."""
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /income <amount> [note]")
        return

    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount.")
        return

    note = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    group_id = get_user_group_id(user_id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO income (timestamp, user, amount, note, group_id) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, amount, note, group_id),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"💰 Income added: *{amount}*", parse_mode="Markdown")


# ===================== LIST COMMANDS =====================

@require_group
async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List current month's expenses."""
    group_id = get_user_group_id(update.effective_user.id)
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    current_month = datetime.now().strftime("%Y-%m")
    cursor.execute(
        "SELECT timestamp, user, amount, category, note FROM expenses WHERE group_id=? AND timestamp LIKE ?",
        (group_id, f"{current_month}%"),
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 No expenses recorded this month.")
        return

    text = "📋 *This Month's Expenses:*\n\n"
    for row in rows:
        timestamp, user, amount, category, note = row
        text += f"- {timestamp} | {user} | {amount} | {category} | {note}\n"

    await update.message.reply_text(text, parse_mode="HTML")


@require_group
async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List category budgets."""
    group_id = get_user_group_id(update.effective_user.id)
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("SELECT category, limit_amount FROM budgets WHERE group_id=?", (group_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 No budgets set yet.")
        return

    text = "📊 *Category Budgets:*\n\n"
    for row in rows:
        category, limit_amount = row
        text += f"- {category}: {limit_amount}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


@require_group
async def set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set a budget for a category."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setbudget <category> <limit>")
        return

    category = context.args[0]
    try:
        limit = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid limit amount.")
        return

    group_id = get_user_group_id(update.effective_user.id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO budgets (category, limit_amount, group_id) VALUES (?, ?, ?)",
        (category, limit, group_id),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"📊 Budget set for *{category}*: {limit}", parse_mode="Markdown")


# ===================== RESET COMMANDS =====================

@require_group
async def reset_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask confirmation to reset group data."""
    await update.message.reply_text("⚠️ Are you sure you want to reset all group data?\nType /confirmreset to confirm.")


@require_group
async def confirm_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset all group data after confirmation."""
    group_id = get_user_group_id(update.effective_user.id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM expenses WHERE group_id=?", (group_id,))
    cursor.execute("DELETE FROM income WHERE group_id=?", (group_id,))
    cursor.execute("DELETE FROM budgets WHERE group_id=?", (group_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text("🗑️ All group data has been reset!")


# ===================== EXPORT COMMAND =====================

@require_group
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export all data for the group."""
    group_id = get_user_group_id(update.effective_user.id)
    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT timestamp, user, amount, category, note FROM expenses WHERE group_id=?",
        (group_id,),
    )
    expenses = cursor.fetchall()

    cursor.execute(
        "SELECT timestamp, user, amount, note FROM income WHERE group_id=?",
        (group_id,),
    )
    income = cursor.fetchall()

    conn.close()

    # Format data for export
    text = "📤 *Export Data:*\n\n*Expenses:*\n"
    for row in expenses:
        text += f"- {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}\n"

    text += "\n*Income:*\n"
    for row in income:
        text += f"- {row[0]} | {row[1]} | {row[2]} | {row[3]}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ===================== HELP COMMAND =====================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help text with emojis."""
    help_text = """
ℹ️ *Available Commands:*

👥 /startgroup <name> – Create or join a group  
👀 /mygroup – Show your current group  
📋 /listgroups – List all groups  
🔄 /switchgroup <name> – Switch to another group  

👥 /listusers – List users in your group  
🗑️ /removeuser <username> – Remove a user from group  

💸 /add <amount> <category> [note] – Add an expense  
💰 /income <amount> [note] – Add an income  

📊 /list – Show this month’s expenses  
📂 /categories – Show budgets for categories  
🎯 /setbudget <category> <limit> – Set budget for category  

⚠️ /reset – Reset group data (asks confirmation)  
✅ /confirmreset – Confirm group reset  

📤 /export – Export all group data  
❓ /help – Show this help message
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")
