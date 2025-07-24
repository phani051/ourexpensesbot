import os
import asyncio
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import ApplicationBuilder, CommandHandler

from db import init_db
from config import BOT_TOKEN
from menu import set_bot_commands
from commands import (
    startgroup, mygroup, listusers, remove_user, listgroups, switchgroup,
    add_expense, add_income, list_expenses, list_categories, set_budget,
    reset_group, confirm_reset, help_command, export_data, summary
)
from scheduler import auto_export_last_month


# -------- Register command handlers --------
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
    app.add_handler(CommandHandler("summary", summary))


# -------- Set Webhook with Telegram --------
def set_webhook():
    render_url = os.getenv("RENDER_URL", "").rstrip("/")
    if not render_url:
        print("⚠️ RENDER_URL not set — webhook will not be configured.")
        return

    webhook_url = f"{render_url}/{BOT_TOKEN}"
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"

    print(f"Registering webhook: {webhook_url}")
    try:
        resp = requests.get(api_url)
        print("Webhook set response:", resp.json())
    except Exception as e:
        print("Error setting webhook:", e)


# -------- Startup callback --------
async def on_startup(app):
    # Set bot commands
    await set_bot_commands(app)

    # Start scheduled job
    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_export_last_month, "cron", hour=0, minute=10, args=[app])
    scheduler.start()
    print("Scheduler started.")

    # Set webhook
    set_webhook()


# -------- Main entry --------
def main():
    init_db()

    # Build application
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    # Register handlers
    register_handlers(app)

    # Webhook parameters
    port = int(os.environ.get("PORT", 5000))
    render_url = os.getenv("RENDER_URL", "").rstrip("/")
    webhook_url = f"{render_url}/{BOT_TOKEN}"

    print(f"Starting webhook server on port {port} for URL {webhook_url}")

    # Run webhook server (aiohttp built-in)
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT_TOKEN,
        webhook_url=webhook_url,
    )


if __name__ == "__main__":
    main()
