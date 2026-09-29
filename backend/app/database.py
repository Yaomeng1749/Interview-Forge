from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

SCHEMA_VERSION = "001_initial"


def default_database_url() -> str:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'trainer.db'}"


def create_database(url: str | None = None) -> tuple[Engine, sessionmaker[Session]]:
    database_url = url or os.getenv("DATABASE_URL") or default_database_url()
    connect_args = (
        {"check_same_thread": False, "timeout": 30} if database_url.startswith("sqlite") else {}
    )
    engine = create_engine(database_url, connect_args=connect_args)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=30000")
            finally:
                cursor.close()

    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def run_migrations(engine: Engine) -> None:
    """Apply the append-only schema version; safe on every local startup."""
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) "
                "VALUES (:version, CURRENT_TIMESTAMP)"
            ),
            {"version": SCHEMA_VERSION},
        )
