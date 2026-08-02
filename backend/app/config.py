import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings:
    MONGO_URL = os.environ["MONGO_URL"]
    DB_NAME = os.environ["DB_NAME"]
    JWT_SECRET = os.environ["JWT_SECRET"]
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_MINUTES = 60
    REFRESH_TOKEN_DAYS = 7
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@midgate.io")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin123!")
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    EDGE_HOST = os.environ.get("EDGE_HOST", "edge.midgate.io")
    DOMAIN_VERIFY_PREFIX = os.environ.get("DOMAIN_VERIFY_PREFIX", "_midgate-challenge")
    IPINTEL_SECRET = os.environ["IPINTEL_SECRET"]


settings = Settings()
