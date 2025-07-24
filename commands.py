import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from utils import get_user_group_id, require_group
from utils import get_current_month
import os
import pandas as pd
from utils import require_admin

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

@require_admin
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

@require_admin
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

@require_admin
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

@require_admin
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
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /add <amount> <category> [note]")
        return

    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Amount must be a number.")
        return

    category = context.args[1]
    note = " ".join(context.args[2:]) if len(context.args) > 2 else ""

    user = update.effective_user.username or update.effective_user.first_name
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    group_id = get_user_group_id(update.effective_user.id)

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (timestamp, user, amount, category, note, group_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (timestamp, user, amount, category, note, group_id))

    # Check total expenses for this category in current month
    current_month = get_current_month()
    cursor.execute("""
        SELECT SUM(amount) FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ? AND category = ? AND group_id = ?
    """, (current_month, category, group_id))
    total_expense = cursor.fetchone()[0] or 0

    # Get budget for this category
    cursor.execute("""
        SELECT limit_amount FROM budgets
        WHERE category = ? AND group_id = ?
    """, (category, group_id))
    budget_row = cursor.fetchone()

    conn.commit()
    conn.close()

    # Send confirmation
    await update.message.reply_text(f"✅ Added expense: {amount:.2f} for *{category}*", parse_mode="Markdown")

    # Send budget alert if applicable
    if budget_row:
        budget_limit = budget_row[0]
        if total_expense >= budget_limit:
            await update.message.reply_text(f"🔴 *Over budget!* {category} has exceeded the limit ({budget_limit:.2f}).", parse_mode="Markdown")
        elif total_expense >= 0.8 * budget_limit:
            await update.message.reply_text(f"⚠️ *Warning:* {category} is at 80% of its budget ({budget_limit:.2f}).", parse_mode="Markdown")



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
    group_id = get_user_group_id(update.effective_user.id)
    current_month = get_current_month()

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # Fetch expenses
    cursor.execute("""
        SELECT timestamp, user, amount, category, note
        FROM expenses
        WHERE group_id=? AND strftime('%Y-%m', timestamp) = ?
        ORDER BY timestamp DESC
    """, (group_id, current_month))
    rows = cursor.fetchall()

    # Fetch total expenses
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE group_id=? AND strftime('%Y-%m', timestamp) = ?
    """, (group_id, current_month))
    total_expenses = cursor.fetchone()[0] or 0

    # Fetch total income
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM income
        WHERE group_id=? AND strftime('%Y-%m', timestamp) = ?
    """, (group_id, current_month))
    total_income = cursor.fetchone()[0] or 0

    conn.close()

    # Calculate balance
    balance = total_income - total_expenses

    if not rows:
        await update.message.reply_text("No expenses recorded this month. 💡 Use /add to add one!")
        return

    # Build text
    text = "📋 *Monthly Expenses:*\n\n"
    for ts, user, amount, category, note in rows:
        note_text = f" - {note}" if note else ""
        text += f"• `{ts}` - *{user}*: ₹{amount} ({category}){note_text}\n"

    text += "\n---\n"
    text += f"💰 *Income:* ₹{total_income}\n"
    text += f"💸 *Expenses:* ₹{total_expenses}\n"
    text += f"🏦 *Balance:* ₹{balance}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


@require_group
async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_id = get_user_group_id(update.effective_user.id)
    current_month = get_current_month()

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # Fetch total expenses grouped by category for the month
    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ? AND group_id = ?
        GROUP BY category
    """, (current_month, group_id))
    expenses_data = cursor.fetchall()

    # Fetch budgets for this group
    cursor.execute("""
        SELECT category, limit_amount
        FROM budgets
        WHERE group_id = ?
    """, (group_id,))
    budgets = dict(cursor.fetchall())  # {category: limit_amount}

    conn.close()

    # If no expenses exist at all
    if not expenses_data and not budgets:
        await update.message.reply_text("No expenses or budgets found for this month.")
        return

    # Build response
    text = "📊 *Category Summary*\n\n"
    for category, total in expenses_data:
        budget_text = ""
        warning_icon = ""

        if category in budgets:
            limit = budgets[category]
            # Check budget status
            if total >= limit:
                warning_icon = " 🔴"  # Over budget
            elif total >= 0.8 * limit:
                warning_icon = " ⚠️"  # Approaching limit

            budget_text = f" (Budget: {limit:.2f})"

        text += f"• {category}: {total:.2f}{budget_text}{warning_icon}\n"

    # Show any budgets with no expenses
    for category, limit in budgets.items():
        if category not in [row[0] for row in expenses_data]:
            text += f"• {category}: 0.00 (Budget: {limit:.2f})\n"

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
    group_id = get_user_group_id(update.effective_user.id)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"export_{now}.xlsx"

    conn = sqlite3.connect("expenses.db")

    # Expenses
    expenses_df = pd.read_sql_query(
        "SELECT timestamp, user, amount, category, note FROM expenses WHERE group_id = ?",
        conn,
        params=(group_id,)
    )

    # Income
    income_df = pd.read_sql_query(
        "SELECT timestamp, user, amount, note FROM income WHERE group_id = ?",
        conn,
        params=(group_id,)
    )

    conn.close()

    # Save to Excel with two sheets
    with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
        expenses_df.to_excel(writer, sheet_name="Expenses", index=False)
        income_df.to_excel(writer, sheet_name="Income", index=False)

    # Send the file
    with open(filename, "rb") as f:
        await update.message.reply_document(f, filename=filename, caption="📊 Exported Income & Expenses")

    # Clean up
    os.remove(filename)

@require_group
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show monthly summary: income, expenses, balance"""
    group_id = get_user_group_id(update.effective_user.id)
    current_month = get_current_month()

    conn = sqlite3.connect("expenses.db")
    cursor = conn.cursor()

    # Total income
    cursor.execute("""
        SELECT SUM(amount) FROM income
        WHERE strftime('%Y-%m', timestamp) = ? AND group_id = ?
    """, (current_month, group_id))
    total_income = cursor.fetchone()[0] or 0

    # Total expenses
    cursor.execute("""
        SELECT SUM(amount) FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ? AND group_id = ?
    """, (current_month, group_id))
    total_expenses = cursor.fetchone()[0] or 0

    # Balance
    balance = total_income - total_expenses

    # Per-category breakdown (optional)
    cursor.execute("""
        SELECT category, SUM(amount) FROM expenses
        WHERE strftime('%Y-%m', timestamp) = ? AND group_id = ?
        GROUP BY category
    """, (current_month, group_id))
    category_data = cursor.fetchall()

    conn.close()

    # Format summary
    text = f"📊 *Monthly Summary ({current_month})*\n\n"
    text += f"💰 *Income:* `{total_income:.2f}`\n"
    text += f"💸 *Expenses:* `{total_expenses:.2f}`\n"
    text += f"🏦 *Balance:* `{balance:.2f}`\n\n"

    if category_data:
        text += "*By Category:*\n"
        for category, amount in category_data:
            text += f"  • {category}: `{amount:.2f}`\n"

    await update.message.reply_text(text, parse_mode="Markdown")



# ===================== HELP COMMAND =====================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Available Commands:*\n\n"
        "🏠 /startgroup `<name>` - Create or join a group\n"
        "👥 /mygroup - Show your current group\n"
        "📋 /listgroups – List all groups\n"
        "📋 /listusers - List users in your group\n"
        "❌ /removeuser `<username>` - Remove a user from group\n"
        "🔄 /switchgroup `<name>` - Switch between groups\n"
        "➕ /add `<amount> <category> [note]` - Add an expense\n"
        "💵 /income `<amount> [note]` - Add income\n"
        "📜 /list - List current month expenses\n"
        "📊 /categories - Show category-wise budgets and usage\n"
        "🎯 /setbudget `<category> <amount>` - Set budget for a category\n"
        "♻ /reset - Reset all group data\n"
        "✅ /confirmreset - Confirm reset after /reset\n"
        "📂 /export - Export data to Excel\n"
        "📑 /summary - Monthly summary (income, expenses, balance)\n"
        "ℹ️ /help - Show this help message\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
