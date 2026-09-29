#!/usr/bin/env python3
"""Safely remove unused v1 generated questions after curated inventory is present.

Never run this automatically. `--apply` intentionally has a 100-question gate,
and it never touches attempts, exam sessions, frozen snapshots, or results.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import delete, func, select

from app.database import create_database, run_migrations
from app.models import Attempt, DrillSession, Question, ReviewQueue, utcnow


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    engine, factory = create_database(); run_migrations(engine)
    with factory() as db:
        curated = db.scalar(select(func.count()).select_from(Question).where(
            Question.version >= 2, Question.verified.is_(True)
        )) or 0
        legacy_ids = list(db.scalars(select(Question.id).where(
            Question.version < 2, ~Question.id.in_(select(Attempt.question_id))
        )))
        active_drills = list(db.scalars(select(DrillSession).where(DrillSession.status == "active")))
        affected = [drill for drill in active_drills if set(drill.question_ids).intersection(legacy_ids)]
        print({"curated_active": curated, "legacy_unattempted": len(legacy_ids), "active_drills_to_finish": len(affected), "apply": args.apply})
        if args.dry_run: return 0
        if curated < 100:
            raise SystemExit("refusing --apply: fewer than 100 active curated questions")
        if legacy_ids:
            db.execute(delete(ReviewQueue).where(ReviewQueue.question_id.in_(legacy_ids)))
            for drill in affected:
                drill.status = "finished"; drill.finished_at = utcnow()
            db.execute(delete(Question).where(Question.id.in_(legacy_ids)))
        db.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
