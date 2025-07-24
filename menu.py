# menu.py
from telegram import BotCommand

async def set_bot_commands(app):
    commands = [
        BotCommand("startgroup", "Create or join a group"),
        BotCommand("mygroup", "Show your current group"),
        BotCommand("add", "Add expense"),
        BotCommand("setbudget", "Set category budget"),
        BotCommand("list", "List current month expenses"),
        BotCommand("categories", "Show categories & budgets"),
        BotCommand("reset", "Reset group data"),
        BotCommand("help", "Show help"),
        BotCommand("export", "Export data to Excel")
    ]
    await app.bot.set_my_commands(commands)
