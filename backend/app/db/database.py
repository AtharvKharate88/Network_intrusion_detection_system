import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{BACKEND_DIR / 'nids.db'}"

try:
    if DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
        )
    else:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        # Test connection to ensure host resolves and credentials work
        with engine.connect():
            pass
except Exception as e:
    # Fallback to local SQLite when remote database (e.g. Neon) is unreachable or offline
    print(f"Primary database connection failed ({e}). Falling back to local SQLite database.")
    fallback_url = f"sqlite:///{BACKEND_DIR / 'nids.db'}"
    engine = create_engine(
        fallback_url,
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass
