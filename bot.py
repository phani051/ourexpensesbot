import os
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
)
from flask import Flask, request

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
    summary
)
from scheduler import auto_export_last_month

# -------- Flask Initialization --------
app_flask = Flask(__name__)

# -------- Telegram Bot Initialization --------
application = ApplicationBuilder().token(BOT_TOKEN).build()

# -------- Register Command Handlers --------
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

register_handlers(application)

# -------- Auto-set Webhook --------
def set_webhook():
    render_url = os.getenv("RENDER_URL", f"https://{os.getenv('RENDER_EXTERNAL_URL', '')}")
    if not render_url:
        print("⚠️ RENDER_URL not set — webhook not configured")
        return

    webhook_url = f"{render_url}/{BOT_TOKEN}"
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"

    try:
        response = requests.get(api_url)
        print("Webhook set response:", response.json())
    except Exception as e:
        print("Error setting webhook:", e)

# -------- Startup Hook --------
async def on_startup():
    await set_bot_commands(application)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_export_last_month, "cron", hour=0, minute=10, args=[application])
    scheduler.start()
    print("Scheduler started.")

    # Auto-set webhook when app starts
    set_webhook()

# -------- Flask Endpoints --------
@app_flask.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_update = request.get_json(force=True)
    update = Update.de_json(json_update, application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

@app_flask.route("/", methods=['GET'])
def index():
    return "Bot is running via webhook!", 200

# -------- Main Entrypoint --------
def main():
    init_db()
    port = int(os.environ.get("PORT", 5000))

    application.post_init(on_startup)

    # Start Flask app (Telegram sends updates here)
    app_flask.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
