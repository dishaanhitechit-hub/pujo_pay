import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Resolve .env relative to this file's location so it works
# regardless of which directory the flask CLI is invoked from.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class BaseConfig:
    SECRET_KEY = os.environ["SECRET_KEY"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # detect stale connections before use
        "pool_recycle": 300,     # recycle connections every 5 min (avoids OS-level drops)
        "pool_size": 10,
        "max_overflow": 5,
    }
    JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
    # Base for all file storage: /srv/pujo-backend/{org_slug}/media and /pdf
    STORAGE_BASE = os.getenv("STORAGE_BASE", "/srv/pujo-backend")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB upload limit
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", 8))
    )
    # Store revoked tokens in-process; swap for Redis in production if needed
    JWT_BLOCKLIST_ENABLED = True
    JWT_BLOCKLIST_TOKEN_CHECKS = ["access"]

    # ── WhatsApp (Meta Cloud API) ──────────────────────────────
    WHATSAPP_TOKEN           = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "1308933112312547")
    # Public base URL used when building links for external services (e.g. Meta fetching images)
    SITE_URL = os.getenv("SITE_URL", "").rstrip("/")

    # ── Email (SMTP) ───────────────────────────────────────────
    MAIL_SERVER    = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT      = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS   = os.getenv("MAIL_USE_TLS", "true")
    MAIL_USERNAME  = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD  = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM_EMAIL = os.getenv("MAIL_FROM_EMAIL", os.getenv("MAIL_USERNAME", ""))
    MAIL_FROM_NAME  = os.getenv("MAIL_FROM_NAME", "PujoPay Platform")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://pujo_user:password@localhost:5432/pujo_pay"
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]


_configs = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return _configs.get(env, DevelopmentConfig)
