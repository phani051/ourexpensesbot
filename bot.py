import os
import threading
import asyncio
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler
from flask import Flask, request, jsonify

from db import init_db
from config import BOT_TOKEN
from menu import set_bot_commands
from commands import (
    startgroup, mygroup, listusers, remove_user, listgroups, switchgroup,
    add_expense, add_income, list_expenses, list_categories, set_budget,
    reset_group, confirm_reset, help_command, export_data, summary
)
from scheduler import auto_export_last_month

# -------- Flask App --------
app_flask = Flask(__name__)

# -------- Telegram Bot --------
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Register handlers
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

# -------- Webhook Setup --------
def set_webhook():
    render_url = os.getenv("RENDER_URL", "")
    if not render_url:
        print("⚠️ RENDER_URL not set — webhook will not be configured.")
        return

    webhook_url = f"{render_url}/{BOT_TOKEN}"
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    print(f"Setting webhook to {webhook_url}")
    try:
        resp = requests.get(api_url)
        print("Webhook set response:", resp.json())
    except Exception as e:
        print("Error setting webhook:", e)

# -------- Startup for PTB --------
async def bot_startup():
    await set_bot_commands(application)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_export_last_month, "cron", hour=0, minute=10, args=[application])
    scheduler.start()
    print("Scheduler started.")
    set_webhook()

    await application.initialize()
    await application.start()
    print("Telegram bot started (webhook mode).")

# Run bot in background thread
def start_bot_thread():
    asyncio.run(bot_startup())

# -------- Flask Endpoints --------
@app_flask.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    print("Webhook called!")
    json_update = request.get_json(force=True)
    print("Update received:", json_update)
    update = Update.de_json(json_update, application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

@app_flask.route("/", methods=['GET'])
def index():
    return "Bot is running via webhook!", 200

@app_flask.route("/debug", methods=['GET'])
def debug_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    try:
        return jsonify(requests.get(url).json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------- Main --------
def main():
    try:
        print("Initializing DB...")
        init_db()

        # Start PTB bot in background
        threading.Thread(target=start_bot_thread, daemon=True).start()

        # Start Flask server (Render detects this port)
        port = int(os.environ.get("PORT", 5000))
        print(f"Starting Flask server on port {port}...")
        app_flask.run(host="0.0.0.0", port=port)
    except Exception as e:
        print("Fatal error on startup:", e)

if __name__ == "__main__":
    main()
