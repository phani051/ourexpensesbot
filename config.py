# config.py
from dotenv import load_dotenv
import os
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
DB_NAME = "expenses.db"
# BOT_TOKEN = "8483908440:AAEgmpviJMCb9xPE8u0Hwhd2on79eX6ATVs"
# ADMIN_ID = "7414452859"



