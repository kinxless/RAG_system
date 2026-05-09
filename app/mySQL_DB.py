import os
import mysql.connector
from urllib.parse import urlparse


def _load_env():
    env_path = ".env"
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


def get_connection():
    """
    Create MySQL connection using DATABASE_URL.
    Expected format: mysql://user:password@host:port/database
    """

    _load_env()

    DATABASE_URL = os.getenv("DATABASE_URL")

    if not DATABASE_URL:
        raise Exception(
            "DATABASE_URL environment variable not set."
        )

    parsed = urlparse(DATABASE_URL)

    password = parsed.password or ""

    conn = mysql.connector.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=parsed.username,
        password=password,
        database=parsed.path.lstrip("/"),
    )

    return conn
