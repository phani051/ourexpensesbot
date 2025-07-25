# bot.py
#from dotenv import load_dotenv
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler
)

from db import init_db
from config import BOT_TOKEN
from menu import set_bot_commands
from commands import (
    startgroup,
    mygroup,
    listusers,
    remove_user,
    listgroups,
    switchgroup,
    add_expense,
    add_income,
    list_expenses,
    list_categories,
    set_budget,
    reset_group,
    confirm_reset,
    help_command,
    export_data,
    summary,
    set_timezone
)
from scheduler import auto_export_last_month

#load_dotenv()  # Load from .env in local development
# Register command handlers
def register_handlers(app):
    app.add_handler(CommandHandler("startgroup", startgroup))
    app.add_handler(CommandHandler("mygroup", mygroup))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("listgroups", listgroups))
    app.add_handler(CommandHandler("switchgroup", switchgroup))
    app.add_handler(CommandHandler("add", add_expense))
    app.add_handler(CommandHandler("income", add_income))
    app.add_handler(CommandHandler("list", list_expenses))
    app.add_handler(CommandHandler("categories", list_categories))
    app.add_handler(CommandHandler("setbudget", set_budget))
    app.add_handler(CommandHandler("reset", reset_group))
    app.add_handler(CommandHandler("confirmreset", confirm_reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("export", export_data))
    app.add_handler(CommandHandler("settimezone", set_timezone))
    app.add_handler(CommandHandler("summary", summary))


# Hook called after bot initialization
async def on_startup(app):
    # Set bot commands
    await set_bot_commands(app)

    # Start scheduler (now inside event loop)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_export_last_month, "cron", hour=0, minute=10, args=[app])
    scheduler.start()
    print("Scheduler started.")


def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    register_handlers(app)

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
