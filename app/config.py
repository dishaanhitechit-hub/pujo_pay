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
    JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
    PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "/srv/pujo/recipet/storages/pdf")
    MEDIA_STORAGE_PATH = os.getenv("MEDIA_STORAGE_PATH", "/srv/pujo/media")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB upload limit
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", 8))
    )
    # Store revoked tokens in-process; swap for Redis in production if needed
    JWT_BLOCKLIST_ENABLED = True
    JWT_BLOCKLIST_TOKEN_CHECKS = ["access"]


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
