# config.py
from dotenv import load_dotenv
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
DB_NAME = "expenses.db"




