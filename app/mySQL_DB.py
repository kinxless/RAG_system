import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    """
    Create PostgreSQL connection using Neon DATABASE_URL.
    """

    DATABASE_URL = os.getenv("postgresql://neondb_owner:npg_hPiO3XzGuZt2@ep-steep-bread-alwp3dk1.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require")

    if not DATABASE_URL:
        raise Exception(
            "DATABASE_URL environment variable not set."
        )

    conn = psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        cursor_factory=RealDictCursor
    )

    return conn