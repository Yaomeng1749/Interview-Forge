from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    topic: Mapped[str] = mapped_column(String, index=True)
    concept: Mapped[str] = mapped_column(String, index=True)
    family_id: Mapped[str | None] = mapped_column(String, nullable=True)
    difficulty: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String, index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    bookmarked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    paper_index: Mapped[int] = mapped_column(Integer, default=1)
    template_id: Mapped[str] = mapped_column(String, index=True)
    locale: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    time_limit_sec: Mapped[int] = mapped_column(Integer, default=3600)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    frozen_questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    revisions: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    flags: Mapped[dict[str, bool]] = mapped_column(JSON, default=dict)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("exam_id", "position", name="uq_attempt_exam_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    exam_id: Mapped[str | None] = mapped_column(
        ForeignKey("exam_sessions.id"), nullable=True, index=True
    )
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_answer: Mapped[dict[str, Any]] = mapped_column(JSON)
    is_correct: Mapped[bool] = mapped_column(Boolean, index=True)
    response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ConceptMastery(Base):
    __tablename__ = "concept_mastery"
    __table_args__ = (UniqueConstraint("domain", "concept", name="uq_mastery_domain_concept"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    concept: Mapped[str] = mapped_column(String, index=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    weighted_mastery: Mapped[float] = mapped_column(Float, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    streak_correct: Mapped[int] = mapped_column(Integer, default=0)
    streak_wrong: Mapped[int] = mapped_column(Integer, default=0)


class ReviewQueue(Base):
    __tablename__ = "review_queue"

    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    reason: Mapped[str] = mapped_column(String)
    due_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    repeat_count: Mapped[int] = mapped_column(Integer, default=0)


class DrillSession(Base):
    __tablename__ = "drill_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    locale: Mapped[str] = mapped_column(String)
    question_ids: Mapped[list[str]] = mapped_column(JSON)
    position: Mapped[int] = mapped_column(Integer, default=0)
    answers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class DecisionLog(Base):
    __tablename__ = "decision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer)
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
