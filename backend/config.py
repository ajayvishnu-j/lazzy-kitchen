"""
Centralized, environment-based configuration for Hotel Lazzy-Kitchen backend.
No secrets are hardcoded here — everything comes from environment variables.
"""
import os
from datetime import timedelta


class Config:
    # --- MySQL ---
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "mysql")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "lazzy_kitchen")
    MYSQL_USER = os.environ.get("MYSQL_USER", "lazzy_user")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # --- Slack ---
    SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

    # --- Flask ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # --- Customer session cookie (signed by SECRET_KEY) ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    # --- Staff API (order status updates). Empty = staff endpoints disabled. ---
    STAFF_API_KEY = os.environ.get("STAFF_API_KEY", "")

    # --- CORS ---
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost").split(",")

    # --- Business config defaults (overridable via restaurant_config table) ---
    TAX_PERCENT_DEFAULT = float(os.environ.get("TAX_PERCENT_DEFAULT", 5.0))

    # --- Demo payment credentials (NEVER real, NEVER stored in DB) ---
    DEMO_CARD_NUMBER = "1234 4321 5678 8765"
    DEMO_PIN = "4321"
    DEMO_CVV = "123"

    # --- Ordering rules ---
    MAX_QTY_PER_ITEM = 20
    MAX_DISTINCT_ITEMS = 30
    RESTAURANT_TIMEZONE = os.environ.get("RESTAURANT_TIMEZONE", "Asia/Kolkata")
    PREP_BUFFER_DEFAULT = int(os.environ.get("PREP_BUFFER_DEFAULT", 5))  # minutes; DB value wins

    # --- Demo Google Pay QR simulation ---
    DEMO_QR_WAIT_SECONDS = 10          # customer must wait this long (enforced server-side)
    DEMO_QR_TOKEN_TTL_SECONDS = 900
