from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.grading import grade_answer
from app.models import Attempt, ConceptMastery, ExamSession, ReviewQueue, utcnow


def submit_exam(session: Session, exam: ExamSession) -> dict[str, Any]:
    """Grade and update all learning state in the caller's single transaction."""
    if exam.result is not None:
        return exam.result

    claim = session.execute(
        update(ExamSession)
        .where(ExamSession.id == exam.id, ExamSession.status == "active")
        .values(status="submitting")
        .execution_options(synchronize_session=False)
    )
    if claim.rowcount != 1:
        session.rollback()
        session.refresh(exam)
        if exam.result is not None:
            return exam.result
        raise RuntimeError(f"exam {exam.id} cannot be submitted from status {exam.status}")

    correct_count = 0
    score = 0
    details: list[dict[str, Any]] = []
    type_totals = {"single_choice": 0, "fill_blank": 0}
    type_correct = {"single_choice": 0, "fill_blank": 0}
    difficulty_totals: dict[str, int] = {}
    difficulty_correct: dict[str, int] = {}
    topic_totals: dict[str, int] = {}
    topic_correct: dict[str, int] = {}
    now = utcnow()
    for position, question in enumerate(exam.frozen_questions, 1):
        response = exam.answers.get(str(position))
        correct = grade_answer(question, response)
        correct_count += int(correct)
        score += (2 if question["type"] == "single_choice" else 4) * int(correct)
        type_totals[question["type"]] += 1
        type_correct[question["type"]] += int(correct)
        difficulty = question["difficulty"]
        difficulty_totals[difficulty] = difficulty_totals.get(difficulty, 0) + 1
        difficulty_correct[difficulty] = difficulty_correct.get(difficulty, 0) + int(correct)
        topic = question["topic"]
        topic_totals[topic] = topic_totals.get(topic, 0) + 1
        topic_correct[topic] = topic_correct.get(topic, 0) + int(correct)
        session.add(
            Attempt(
                question_id=question["id"],
                exam_id=exam.id,
                position=position,
                user_answer=response or {},
                is_correct=correct,
                attempted_at=now,
            )
        )
        update_learning_state(session, question, correct, now)
        details.append(
            {
                "position": position,
                "id": question["id"],
                "prompt": question.get("prompt", ""),
                "options": question.get("options", []),
                "locale": question.get("locale", exam.locale),
                "response": response,
                "user_answer": _display_answer(response),
                "is_correct": correct,
                "correct": correct,
                "answer": question.get("answer"),
                "correct_answer": _display_answer(question.get("answer")),
                "accepted_answers": question.get("accepted_answers", []),
                "explanation": question.get("explanation", ""),
                "distractor_explanations": question.get("distractor_explanations", {}),
                "takeaway": question.get("takeaway"),
                "knowledge_card": question.get("knowledge_card"),
                "domain": question["domain"],
                "topic": question["topic"],
                "concept": question["concept"],
                "difficulty": question["difficulty"],
                "type": question["type"],
            }
        )
    exam.finished_at = now
    exam.status = "submitted"
    exam.score = score
    exam.correct_count = correct_count
    elapsed_seconds = max(0, int((now - exam.started_at).total_seconds()))
    exam.result = {
        "exam_id": exam.id,
        "score": score,
        "total_score": 100,
        "correct_count": correct_count,
        "total_questions": len(exam.frozen_questions),
        "elapsed_seconds": elapsed_seconds,
        "choice_accuracy": _ratio(type_correct["single_choice"], type_totals["single_choice"]),
        "fill_accuracy": _ratio(type_correct["fill_blank"], type_totals["fill_blank"]),
        "difficulty_breakdown": {
            key: _ratio(difficulty_correct.get(key, 0), total)
            for key, total in sorted(difficulty_totals.items())
        },
        "topic_breakdown": {
            key: _ratio(topic_correct.get(key, 0), total)
            for key, total in sorted(topic_totals.items())
        },
        "finished_at": now.isoformat(),
        "questions": details,
    }
    session.commit()
    return exam.result


def update_learning_state(
    session: Session,
    question: dict[str, Any],
    correct: bool,
    now: Any | None = None,
) -> None:
    """Apply the same mastery and review policy for exams and rapid drills."""
    observed_at = now or utcnow()
    mastery = session.scalar(
        select(ConceptMastery).where(
            ConceptMastery.domain == question["domain"],
            ConceptMastery.concept == question["concept"],
        )
    )
    if mastery is None:
        mastery = ConceptMastery(
            domain=question["domain"],
            concept=question["concept"],
            attempts=0,
            correct=0,
            weighted_mastery=0,
            streak_correct=0,
            streak_wrong=0,
        )
        session.add(mastery)
    mastery.attempts += 1
    mastery.correct += int(correct)
    mastery.weighted_mastery = mastery.correct / mastery.attempts
    mastery.last_seen_at = observed_at
    queued = session.get(ReviewQueue, question["id"])
    if correct:
        mastery.streak_correct += 1
        mastery.streak_wrong = 0
        if queued:
            queued.interval_days = min(30, max(1, queued.interval_days * 2))
            queued.due_at = observed_at + timedelta(days=queued.interval_days)
        return

    mastery.streak_wrong += 1
    mastery.streak_correct = 0
    mastery.next_review_at = observed_at + timedelta(days=1)
    if queued is None:
        queued = ReviewQueue(
            question_id=question["id"],
            reason="wrong_answer",
            repeat_count=0,
            interval_days=1,
            due_at=observed_at + timedelta(days=1),
        )
        session.add(queued)
    queued.repeat_count += 1
    queued.interval_days = 1
    queued.due_at = observed_at + timedelta(days=1)


def _ratio(correct: int, total: int) -> float:
    return correct / total if total else 0.0


def _display_answer(answer: dict[str, Any] | None) -> str | None:
    if not answer:
        return None
    for key in ("option_id", "text", "canonical"):
        value = answer.get(key)
        if value is not None:
            return str(value)
    return None
