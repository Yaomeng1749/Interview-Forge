#!/usr/bin/env python3
"""Remove every legacy v1 question and its local-only practice traces.

This is an explicit destructive maintenance action for a single-user installation.
It keeps v2 curated/imported inventory and its attempts, but removes old question
rows, their attempts/review entries/drill sessions, and frozen exams containing
old questions so they cannot reappear in the review flow.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import delete, func, select

from app.database import create_database, run_migrations
from app.models import Attempt, ConceptMastery, DrillSession, ExamSession, Question, ReviewQueue


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    engine, factory = create_database()
    run_migrations(engine)
    with factory() as db:
        legacy_ids = set(db.scalars(select(Question.id).where(Question.version < 2)))
        legacy_attempts = db.scalar(
            select(func.count()).select_from(Attempt).where(Attempt.question_id.in_(legacy_ids))
        ) if legacy_ids else 0
        legacy_reviews = db.scalar(
            select(func.count()).select_from(ReviewQueue).where(ReviewQueue.question_id.in_(legacy_ids))
        ) if legacy_ids else 0
        drills = list(db.scalars(select(DrillSession)).all())
        affected_drills = [row.id for row in drills if set(row.question_ids).intersection(legacy_ids)]
        exams = list(db.scalars(select(ExamSession)).all())
        affected_exams = [
            row.id
            for row in exams
            if any(question.get("id") in legacy_ids for question in row.frozen_questions)
        ]
        report = {
            "legacy_questions": len(legacy_ids),
            "legacy_attempts": legacy_attempts or 0,
            "legacy_review_entries": legacy_reviews or 0,
            "drill_sessions_to_delete": len(affected_drills),
            "exam_sessions_to_delete": len(affected_exams),
            "apply": args.apply,
        }
        print(report)
        if args.dry_run:
            return 0
        if legacy_ids:
            db.execute(delete(ReviewQueue).where(ReviewQueue.question_id.in_(legacy_ids)))
            db.execute(delete(Attempt).where(Attempt.question_id.in_(legacy_ids)))
            db.execute(delete(DrillSession).where(DrillSession.id.in_(affected_drills)))
            db.execute(delete(ExamSession).where(ExamSession.id.in_(affected_exams)))
            db.execute(delete(Question).where(Question.id.in_(legacy_ids)))
            # Mastery values are aggregates; rebuild them on future v2 attempts rather
            # than presenting proficiency derived from deleted legacy questions.
            db.execute(delete(ConceptMastery))
        db.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
