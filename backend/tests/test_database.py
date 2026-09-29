from pathlib import Path

from sqlalchemy import text

from app.database import create_database, run_migrations


def test_sqlite_enables_integrity_and_concurrency_pragmas(tmp_path: Path) -> None:
    engine, _ = create_database(f"sqlite:///{tmp_path / 'pragmas.db'}")
    run_migrations(engine)
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() >= 5000
        assert connection.execute(text("PRAGMA journal_mode")).scalar_one().casefold() == "wal"
        assert connection.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()
