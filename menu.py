# menu.py
from telegram import BotCommand

async def set_bot_commands(app):
    commands = [
        BotCommand("startgroup", "🏠 Create a new FamilyGroup"),
        BotCommand("joingroup", "🔑 Join group using invite code"),
        BotCommand("mygroup", "👥 Show your current group"),
        BotCommand("listusers", "📋 List users in your group"),
        BotCommand("removeuser", "❌ Remove a user from group"),
        BotCommand("listgroups", "🌐 List all groups"),
        BotCommand("switchgroup", "🔄 Switch to another group"),
        BotCommand("add", "➕ Add an expense"),
        BotCommand("income", "💵 Add income"),
        BotCommand("list", "📜 List expenses"),
        BotCommand("categories", "📊 Category budgets"),
        BotCommand("setbudget", "🎯 Set budget"),
        BotCommand("settimezone", "🛎 Set timezone for your group"),
        BotCommand("reset", "♻ Reset group data"),
        BotCommand("confirmreset", "✅ Confirm reset"),
        BotCommand("export", "📂 Export data to Excel"),
        BotCommand("summary", "📑 Monthly summary"),  # Emoji added
        
        BotCommand("help", "ℹ️ Show help"),
    ]
    await app.bot.set_my_commands(commands)
