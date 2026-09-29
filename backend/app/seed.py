from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exam_builder import load_questions
from app.models import Question


def resolve_bank_path() -> Path:
    configured = os.getenv("QUESTION_BANK_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "question_bank" / "questions.jsonl"


def resolve_bank_paths(path: Path | None = None) -> list[Path]:
    if path is not None or os.getenv("QUESTION_BANK_PATH"):
        return [path or resolve_bank_path()]
    root = Path(__file__).resolve().parents[2] / "question_bank"
    # Curated packs are deliberately kept separate for human review, then loaded
    # together on startup.  The legacy bank stays append-only for historical rows.
    return [
        root / "questions.jsonl",
        *sorted((root / "curated_sources").glob("*.jsonl")),
        *sorted((root / "curated_packs").glob("*.jsonl")),
    ]


def _question_row(row: dict[str, Any]) -> Question:
    return Question(
        id=row["id"], domain=row["domain"], topic=row["topic"], concept=row["concept"],
        family_id=row.get("question_family_id"), difficulty=row["difficulty"], type=row["type"],
        verified=bool(row.get("verified")), version=int(row.get("version", 1)), payload=row,
    )


def import_bank(session: Session, path: Path | None = None) -> dict[str, object]:
    """Append missing bank IDs only; old user rows and attempt links stay untouched."""
    paths = [item for item in resolve_bank_paths(path) if item.exists()]
    if not paths:
        return {"path": str(path or resolve_bank_path()), "loaded": 0, "inserted": 0,
                "available": False, "message": "question bank not found"}
    rows = [row for bank_path in paths for row in load_questions(bank_path)]
    ids = [row["id"] for row in rows]
    existing_count = len(session.scalars(select(Question.id)).all())
    known = set(session.scalars(select(Question.id).where(Question.id.in_(ids)))) if ids else set()
    inserted = 0
    for row in rows:
        # v1 is the historical seed: a user may intentionally remove unused
        # rows, so startup must never resurrect them in a non-empty database.
        if existing_count and int(row.get("version", 1)) < 2:
            continue
        if row["id"] not in known:
            session.add(_question_row(row)); known.add(row["id"]); inserted += 1
    session.commit()
    loaded = len(session.scalars(select(Question.id)).all())
    return {"path": ",".join(str(item) for item in paths), "loaded": loaded, "inserted": inserted,
            "available": True, "message": "ready"}
