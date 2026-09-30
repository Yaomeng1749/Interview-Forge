from __future__ import annotations

import os
import random
import time
import uuid
from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AliasChoices, BaseModel, Field
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.exam_builder import InventoryShortage, _localize, build_standard_paper
from app.core.grading import grade_answer
from app.database import create_database, run_migrations
from app.decision.base import DecisionResult
from app.decision.router import DecisionRouter
from app.models import (
    Attempt,
    ConceptMastery,
    DecisionLog,
    DrillSession,
    ExamSession,
    Question,
    ReviewQueue,
    Setting,
    utcnow,
)
from app.seed import import_bank
from app.seed import _question_row
from app.question_import import fingerprint, parse_question_content, validate_candidate
from app.services import submit_exam, update_learning_state

SUPPORTED_LOCALES = ("zh-CN", "en-US")
TEMPLATES = [
    {
        "id": "exam-a-sde",
        "name_i18n": {"zh-CN": "SDE 基础综合卷", "en-US": "SDE Fundamentals"},
        "question_count": 40,
        "time_limit_sec": 3600,
    },
    {
        "id": "exam-d-mle",
        "name_i18n": {"zh-CN": "MLE 基础综合卷", "en-US": "MLE Fundamentals"},
        "question_count": 40,
        "time_limit_sec": 3600,
    },
    {
        "id": "exam-g-mixed",
        "name_i18n": {"zh-CN": "MLE + SDE 综合卷", "en-US": "MLE + SDE Mixed"},
        "question_count": 40,
        "time_limit_sec": 3600,
    },
]

CURATED_PACKS = [
    ("curated-a1-sde", "paper_A1_SDE_standard_40", "Curated A1 / SDE", "A1 精选卷 / SDE"),
    ("curated-d1-mle", "paper_D1_MLE_standard_40", "Curated D1 / MLE", "D1 精选卷 / MLE"),
    ("curated-g1-mixed", "paper_G1_Mixed_standard_40", "Curated G1 / Mixed", "G1 精选卷 / 混合"),
    ("curated-g2-mixed", "paper_G2_Mixed_standard_40", "Curated G2 / Mixed", "G2 精选卷 / 混合"),
]
CURATED_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "question_bank" / "curated_packs" / "paper_manifests.json"
DRILL_SOURCE_KINDS = {"curated", "imported", "curated_exam"}


def _load_curated_manifest() -> dict[str, list[str]]:
    import json

    with CURATED_MANIFEST_PATH.open(encoding="utf-8") as source:
        payload = json.load(source)
    return payload


class BuildRequest(BaseModel):
    template_id: str = "exam-g-mixed"
    locale: Literal["zh-CN", "en-US"] = "zh-CN"
    seed: int | None = None
    paper_count: int = Field(default=1, ge=1, le=20)
    difficulty_preset: Literal["foundation", "standard", "intensive", "hard"] = "standard"
    timed: bool = True
    randomize_questions: bool = Field(
        default=True,
        validation_alias=AliasChoices("randomize_questions", "random_question_order"),
    )
    randomize_options: bool = Field(
        default=False,
        validation_alias=AliasChoices("randomize_options", "random_option_order"),
    )
    allow_review: bool = Field(
        default=True,
        validation_alias=AliasChoices("allow_review", "allow_review_answered"),
    )


class ReviewBuildRequest(BuildRequest):
    mode: Literal["wrong", "due", "bookmarked"] = Field(
        default="wrong", validation_alias=AliasChoices("mode", "kind")
    )


class SaveAnswerRequest(BaseModel):
    revision: int = Field(ge=1, validation_alias=AliasChoices("revision", "client_revision"))
    answer: dict[str, Any] | str


class FlagRequest(BaseModel):
    flagged: bool
    client_revision: int | None = Field(default=None, ge=1)


class SubmitRequest(BaseModel):
    client_revision: int = Field(default=0, ge=0)
    answer_revisions: dict[int, int] = Field(default_factory=dict)


class SettingsRequest(BaseModel):
    locale: Literal["zh-CN", "en-US"] | None = None
    daily_target: int | None = Field(
        default=None,
        ge=0,
        le=10000,
        validation_alias=AliasChoices("daily_target", "daily_goal"),
    )


class BookmarkRequest(BaseModel):
    bookmarked: bool


class DrillRequest(BaseModel):
    count: int | None = Field(default=20, ge=1, le=160)
    locale: Literal["zh-CN", "en-US"] = "zh-CN"
    domain: Literal["sde", "mle", "mixed"] | None = None


class DrillAnswerRequest(BaseModel):
    question_id: str | None = None
    position: int | None = Field(default=None, ge=1)
    answer: dict[str, Any] | str
    locale: Literal["zh-CN", "en-US"] | None = None


class QuestionImportRequest(BaseModel):
    filename: str = "questions.jsonl"
    content: str = Field(min_length=1)


def _public_question(
    question: dict[str, Any], position: int | None = None, bookmarked: bool | None = None
) -> dict[str, Any]:
    visible = {
        "id": question["id"],
        "domain": question["domain"],
        "topic": question["topic"],
        "concept": question["concept"],
        "difficulty": question["difficulty"],
        "type": question["type"],
        "prompt": question["prompt"],
        "options": question.get("options", []),
        "locale": question["locale"],
        "question_style": question.get("question_style"),
    }
    if position is not None:
        visible["position"] = position
    if bookmarked is not None:
        visible["bookmarked"] = bookmarked
    return visible


def _bank_public(question: Question, locale: str = "zh-CN") -> dict[str, Any]:
    content = question.payload.get("content_i18n", {}).get(locale) or {}
    return {
        "id": question.id,
        "domain": question.domain,
        "topic": question.topic,
        "concept": question.concept,
        "difficulty": question.difficulty,
        "type": question.type,
        "prompt": content.get("prompt", ""),
        "options": content.get("options", []),
        "verified": question.verified,
        "bookmarked": question.bookmarked,
        "question_style": question.payload.get("question_style"),
        "quality_tier": question.payload.get("quality_tier", "legacy_generated"),
        "source_kind": question.payload.get("source_kind", "legacy_generated"),
        "takeaway": content.get("takeaway"),
        "knowledge_card": content.get("knowledge_card"),
    }


def create_app() -> FastAPI:
    engine, session_factory = create_database()
    bank_status: dict[str, object] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        run_migrations(engine)
        with session_factory() as session:
            bank_status.update(import_bank(session))
            defaults = {"locale": "zh-CN", "daily_target": "160"}
            for key, value in defaults.items():
                if session.get(Setting, key) is None:
                    session.add(Setting(key=key, value=value))
            session.commit()
        yield
        engine.dispose()

    app = FastAPI(title="MLE / SDE Adaptive Exam API", version="0.1.0", lifespan=lifespan)
    app.state.session_factory = session_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:4173",
            "http://localhost:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    def localized_drill_question(
        drill: DrillSession, position: int, locale: str, db: Session
    ) -> tuple[Question, dict[str, Any]]:
        if position < 1 or position > len(drill.question_ids):
            raise HTTPException(409, "question position is outside this drill")
        question = db.get(Question, drill.question_ids[position - 1])
        if question is None:
            raise HTTPException(409, "question inventory changed")
        payload = {
            **question.payload,
            **question.payload["content_i18n"][locale],
            "locale": locale,
        }
        return question, payload

    def localized_drill_feedback(
        question: Question, answer: dict[str, Any], locale: str, *, refreshed_by: str | None = None
    ) -> dict[str, Any]:
        payload = question.payload
        content = payload["content_i18n"][locale]
        correct = bool(answer["is_correct"])
        return {
            **answer,
            "correct": correct,
            "is_correct": correct,
            "correct_answer": _display_answer(payload.get("answer")),
            "explanation": content.get("explanation", ""),
            "distractor_explanations": content.get("distractor_explanations", {}),
            "takeaway": content.get("takeaway"),
            "knowledge_card": content.get("knowledge_card"),
            "locale": locale,
            "decision_refresh": refreshed_by,
        }

    def decision_router() -> DecisionRouter:
        return DecisionRouter(
            api_key=os.getenv("TYPESAFE_API_KEY"),
            typesafe_url=os.getenv("TYPESAFE_URL", "https://api.typesafe.ai/v1/systemone"),
            typesafe_model=os.getenv("TYPESAFE_MODEL", "jev-latest"),
            nano_url=os.getenv("NANOJEV_URL", "http://127.0.0.1:9101"),
            von_url=os.getenv("VON_URL", "http://127.0.0.1:9102"),
        )

    def decision_context(db: Session) -> tuple[dict[str, Any], dict[str, Any]]:
        attempts = list(db.scalars(select(Attempt).order_by(Attempt.id.desc()).limit(200)).all())
        mastery_rows = list(db.scalars(select(ConceptMastery)).all())
        mastery = {row.concept: row.weighted_mastery for row in mastery_rows}
        domain_totals: dict[str, list[int]] = {"sde": [0, 0], "mle": [0, 0]}
        for row in mastery_rows:
            totals = domain_totals.setdefault(row.domain, [0, 0])
            totals[0] += row.attempts
            totals[1] += row.correct
        domain_accuracy = {
            domain: correct / total if total else 0.0
            for domain, (total, correct) in domain_totals.items()
        }
        wrong_ids = [item.question_id for item in attempts if not item.is_correct]
        wrong_questions = (
            list(db.scalars(select(Question).where(Question.id.in_(wrong_ids))).all())
            if wrong_ids
            else []
        )
        inventory_rows = db.execute(
            select(Question.domain, Question.topic, Question.difficulty, func.count())
            .where(Question.verified.is_(True))
            .group_by(Question.domain, Question.topic, Question.difficulty)
        ).all()
        inventory = {
            "verified": sum(row[3] for row in inventory_rows),
            "cells": [
                {"domain": row[0], "topic": row[1], "difficulty": row[2], "count": row[3]}
                for row in inventory_rows
            ],
        }
        return (
            {
                "recent_accuracy": (
                    sum(item.is_correct for item in attempts) / len(attempts) if attempts else 0.7
                ),
                "recent_wrong_topics": list(dict.fromkeys(row.topic for row in wrong_questions)),
                "mastery": mastery,
                "mastered_topics": [key for key, value in mastery.items() if value >= 0.85],
                "uncovered_topics": [key for key, value in mastery.items() if value == 0],
                "core_topics": ["data_structures_algorithms", "classical_ml"],
                "weak_domain": min(domain_accuracy, key=domain_accuracy.get),
            },
            inventory,
        )

    async def evaluate_and_log(
        event: str,
        db: Session,
        *,
        exam_id: str | None = None,
        extra_state: dict[str, Any] | None = None,
    ) -> DecisionResult:
        state, inventory = decision_context(db)
        state.update(extra_state or {})
        started = time.perf_counter()
        decision = await decision_router().evaluate(state, inventory)
        db.add(
            DecisionLog(
                exam_id=exam_id,
                provider=decision.provider,
                model=os.getenv("TYPESAFE_MODEL") if decision.provider == "typesafe-jev" else None,
                latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
                request={"event": event, "state": state, "inventory": inventory},
                response=decision.model_dump(),
                confidence=decision.confidence,
            )
        )
        db.commit()
        return decision

    def retarget_next_drill_block(
        db: Session, drill: DrillSession, decision: DecisionResult
    ) -> None:
        start = drill.position
        end = min(start + 10, len(drill.question_ids))
        target_count = end - start
        if target_count <= 0:
            return
        reserved = set(drill.question_ids[:start] + drill.question_ids[end:])
        current_rows = list(
            db.scalars(select(Question).where(Question.id.in_(drill.question_ids))).all()
        )
        domains = {row.domain for row in current_rows}
        candidate_query = select(Question).where(
            Question.verified.is_(True), ~Question.id.in_(reserved)
        )
        if len(domains) == 1:
            candidate_query = candidate_query.where(Question.domain == next(iter(domains)))
        candidates = list(db.scalars(candidate_query).all())
        attempted_ids = set(db.scalars(select(Attempt.question_id).distinct()))
        quality_candidates = [
            row for row in candidates
            if row.payload.get("selection_status") == "active"
            and row.payload.get("source_kind") in DRILL_SOURCE_KINDS
            and row.id not in attempted_ids
        ]
        if quality_candidates:
            candidates = quality_candidates
        else:
            return
        rng = random.Random(f"{drill.id}:{drill.position}")
        difficulty_pool = [
            difficulty
            for difficulty, quota in decision.difficulty.items()
            for _ in range(max(0, quota))
        ] or ["L1", "L2", "L3"]
        rng.shuffle(difficulty_pool)
        desired = [difficulty_pool[index % len(difficulty_pool)] for index in range(target_count)]
        selected: list[Question] = []
        families_used = {str(row.family_id) for row in current_rows[:start]}
        for difficulty in desired:
            matching = [row for row in candidates if row.difficulty == difficulty and str(row.family_id) not in families_used]
            pool = matching or candidates
            if not pool:
                break
            pool.sort(
                key=lambda row: (
                    -decision.topic_weights.get(
                        row.topic, decision.topic_weights.get(row.concept, 0.0)
                    )
                    + rng.random() * 0.01
                )
            )
            chosen = pool[0]
            selected.append(chosen)
            candidates.remove(chosen)
            families_used.add(str(chosen.family_id))
        if len(selected) == target_count:
            rng.shuffle(selected)
            updated = list(drill.question_ids)
            updated[start:end] = [row.id for row in selected]
            drill.question_ids = updated
            db.commit()

    def freeze_paper(
        source: list[dict[str, Any]],
        *,
        template_id: str,
        locale: str,
        seed: int,
        difficulty_preset: str,
        randomize_questions: bool,
        randomize_options: bool,
        decision: DecisionResult | None,
    ) -> list[dict[str, Any]]:
        curated = next((item for item in CURATED_PACKS if item[0] == template_id), None)
        if curated:
            manifest = _load_curated_manifest()
            ids = manifest.get(curated[1])
            if not ids or len(ids) != 40:
                raise InventoryShortage(f"curated manifest is missing {curated[1]}")
            by_id = {row["id"]: row for row in source}
            missing = [question_id for question_id in ids if question_id not in by_id]
            if missing:
                raise InventoryShortage(f"curated paper is missing {len(missing)} questions")
            frozen = [_localize(by_id[question_id], locale) for question_id in ids]
            rng = random.Random(seed)
            if randomize_questions:
                rng.shuffle(frozen)
            if randomize_options:
                for question in frozen:
                    rng.shuffle(question.get("options", []))
            return frozen
        # Template A/D/G is a user choice. Jev may tune only difficulty and topic coverage.
        effective_template = template_id
        preset_totals = {
            "foundation": {"L1": 20, "L2": 16, "L3": 4},
            "standard": {"L1": 12, "L2": 20, "L3": 8},
            "intensive": {"L1": 6, "L2": 20, "L3": 14},
            "hard": {"L1": 2, "L2": 14, "L3": 24},
        }
        adaptive_difficulty = (
            decision.difficulty
            if decision
            and sum(decision.difficulty.values()) == 40
            and decision.difficulty != preset_totals[difficulty_preset]
            else None
        )
        frozen = build_standard_paper(
            source,
            effective_template,
            locale,
            seed,
            difficulty_preset,
            difficulty_quotas=adaptive_difficulty,
            topic_weights=decision.topic_weights if decision else None,
        )
        if not randomize_questions:
            frozen.sort(
                key=lambda question: (
                    question["type"] == "fill_blank",
                    question["id"],
                )
            )
        if randomize_options:
            option_rng = random.Random(seed)
            for question in frozen:
                option_rng.shuffle(question.get("options", []))
        return frozen

    def latest_exam_decision(db: Session, exam_id: str) -> DecisionResult | None:
        logs = db.scalars(
            select(DecisionLog)
            .where(DecisionLog.exam_id == exam_id)
            .order_by(DecisionLog.id.desc())
        ).all()
        for log in logs:
            if log.request.get("event") == "post_exam":
                return DecisionResult.model_validate(log.response)
        return None

    def get_exam(exam_id: str, db: Session) -> ExamSession:
        exam = db.get(ExamSession, exam_id)
        if exam is None:
            raise HTTPException(404, "exam not found")
        if exam.status == "queued":
            previous = db.scalar(
                select(ExamSession).where(
                    ExamSession.batch_id == exam.batch_id,
                    ExamSession.paper_index == exam.paper_index - 1,
                )
            )
            if previous is not None and previous.status != "submitted":
                raise HTTPException(409, "previous paper must be submitted first")
            if previous is not None:
                decision = latest_exam_decision(db, previous.id)
                if decision is not None:
                    rows = list(
                        db.scalars(select(Question).where(Question.verified.is_(True))).all()
                    )
                    exam.frozen_questions = freeze_paper(
                        [row.payload for row in rows],
                        template_id=exam.template_id,
                        locale=exam.locale,
                        seed=int(exam.configuration.get("seed", 0)),
                        difficulty_preset=str(
                            exam.configuration.get("requested_difficulty", "standard")
                        ),
                        randomize_questions=bool(
                            exam.configuration.get("random_question_order", True)
                        ),
                        randomize_options=bool(
                            exam.configuration.get("random_option_order", False)
                        ),
                        decision=decision,
                    )
                    exam.configuration = {
                        **exam.configuration,
                        "decision": decision.model_dump(),
                        "adapted_from_exam_id": previous.id,
                    }
            started = utcnow()
            exam.status = "active"
            exam.started_at = started
            exam.deadline_at = started + timedelta(
                seconds=exam.time_limit_sec if exam.time_limit_sec else 86400 * 36500
            )
            db.commit()
        if exam.status == "active" and exam.deadline_at <= utcnow():
            submit_exam(db, exam)
        return exam

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok" if bank_status.get("loaded", 0) else "degraded",
            "question_bank": bank_status,
            "database": "ready",
        }

    @app.get("/api/exam-templates")
    def templates(locale: Literal["zh-CN", "en-US"] = "zh-CN") -> dict[str, Any]:
        return {
            "items": [
                {
                    **template,
                    "name": template["name_i18n"][locale],
                    "duration_minutes": template["time_limit_sec"] // 60,
                }
                for template in TEMPLATES
            ] + [
                {
                    "id": template_id,
                    "name": english if locale == "en-US" else chinese,
                    "description": (
                        "Fixed 40-question curated paper; Jev will not reshuffle its membership."
                        if locale == "en-US"
                        else "固定 40 题精选卷；Jev 不会改变题目集合。"
                    ),
                    "question_count": 40,
                    "duration_minutes": 60,
                    "fixed_pack": True,
                }
                for template_id, _, english, chinese in CURATED_PACKS
            ]
        }

    def persist_exams(
        request: BuildRequest,
        db: Session,
        rows: list[Question] | None = None,
        decision: DecisionResult | None = None,
    ) -> dict[str, Any]:
        if rows is None:
            rows = list(db.scalars(select(Question).where(Question.verified.is_(True))).all())
        source = [row.payload for row in rows]
        seed = request.seed if request.seed is not None else random.SystemRandom().randrange(2**31)
        batch_id = uuid.uuid4().hex if request.paper_count > 1 else None
        exams: list[ExamSession] = []
        try:
            for index in range(request.paper_count):
                paper_seed = seed + index
                frozen = freeze_paper(
                    source,
                    template_id=request.template_id,
                    locale=request.locale,
                    seed=paper_seed,
                    difficulty_preset=request.difficulty_preset,
                    randomize_questions=request.randomize_questions,
                    randomize_options=request.randomize_options,
                    decision=decision,
                )
                started = utcnow()
                exam = ExamSession(
                    id=uuid.uuid4().hex,
                    batch_id=batch_id,
                    paper_index=index + 1,
                    template_id=request.template_id,
                    locale=request.locale,
                    started_at=started,
                    deadline_at=started
                    + timedelta(seconds=3600 if request.timed else 86400 * 36500),
                    time_limit_sec=3600 if request.timed else 0,
                    status="active" if index == 0 else "queued",
                    frozen_questions=frozen,
                    answers={},
                    revisions={},
                    flags={},
                    configuration={
                        "timed": request.timed,
                        "requested_template": request.template_id,
                        "requested_difficulty": request.difficulty_preset,
                        "seed": paper_seed,
                        "random_question_order": request.randomize_questions,
                        "random_option_order": request.randomize_options,
                        "allow_back_navigation": request.allow_review,
                        "decision": decision.model_dump() if decision else None,
                    },
                )
                db.add(exam)
                exams.append(exam)
            db.commit()
        except (InventoryShortage, ValueError) as exc:
            db.rollback()
            raise HTTPException(409, str(exc)) from exc
        response: dict[str, Any] = {
            "exam_ids": [exam.id for exam in exams],
            "batch_id": batch_id,
            "paper_count": len(exams),
        }
        if len(exams) == 1:
            response["exam_id"] = exams[0].id
            response["id"] = exams[0].id
        else:
            response["id"] = exams[0].id
        return response

    @app.post("/api/exams/build")
    async def build_exam(request: BuildRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
        if not bank_status.get("loaded"):
            raise HTTPException(409, "question bank is unavailable")
        fixed_pack = any(item[0] == request.template_id for item in CURATED_PACKS)
        if fixed_pack and request.paper_count != 1:
            raise HTTPException(422, "fixed curated papers must be started one at a time")
        decision = None
        if not fixed_pack:
            decision = await evaluate_and_log(
                "pre_exam",
                db,
                extra_state={
                    "requested_template": request.template_id,
                    "requested_difficulty": request.difficulty_preset,
                },
            )
        return persist_exams(request, db, decision=decision)

    @app.get("/api/exams/active")
    def active_exams(db: Session = Depends(get_db)) -> dict[str, Any] | None:
        exams = db.scalars(
            select(ExamSession)
            .where(ExamSession.status == "active")
            .order_by(ExamSession.started_at.desc())
        ).all()
        for exam in exams:
            if exam.deadline_at <= utcnow():
                submit_exam(db, exam)
        active = [exam for exam in exams if exam.status == "active"]
        return _exam_detail_payload(active[0]) if active else None

    @app.get("/api/exams/history")
    def exam_history(db: Session = Depends(get_db)) -> dict[str, Any]:
        exams = db.scalars(select(ExamSession).order_by(ExamSession.started_at.desc())).all()
        return {"items": [_exam_summary(exam) for exam in exams]}

    @app.get("/api/exams/{exam_id}")
    def exam_detail(exam_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        exam = get_exam(exam_id, db)
        return _exam_detail_payload(exam)

    @app.put("/api/exams/{exam_id}/answers/{position}")
    def save_answer(
        exam_id: str, position: int, request: SaveAnswerRequest, db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        exam = get_exam(exam_id, db)
        if exam.status != "active":
            raise HTTPException(409, "exam is already submitted")
        if position < 1 or position > len(exam.frozen_questions):
            raise HTTPException(404, "question position not found")
        current = exam.revisions.get(str(position), 0)
        if request.revision <= current:
            raise HTTPException(409, f"stale revision; current revision is {current}")
        normalized_answer = (
            request.answer
            if isinstance(request.answer, dict)
            else {"option_id": request.answer, "text": request.answer}
        )
        exam.answers = {**exam.answers, str(position): normalized_answer}
        exam.revisions = {**exam.revisions, str(position): request.revision}
        exam.configuration = {
            **exam.configuration,
            "last_client_revision": max(
                int(exam.configuration.get("last_client_revision", 0)), request.revision
            ),
        }
        db.commit()
        return {"position": position, "revision": request.revision, "saved": True}

    @app.put("/api/exams/{exam_id}/flags/{position}")
    def save_flag(
        exam_id: str, position: int, request: FlagRequest, db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        exam = get_exam(exam_id, db)
        if exam.status != "active":
            raise HTTPException(409, "exam is already submitted")
        if position < 1 or position > len(exam.frozen_questions):
            raise HTTPException(404, "question position not found")
        exam.flags = {**exam.flags, str(position): request.flagged}
        db.commit()
        return {"position": position, "flagged": request.flagged}

    @app.post("/api/exams/{exam_id}/submit")
    async def submit(
        exam_id: str,
        request: SubmitRequest | None = None,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        exam = get_exam(exam_id, db)
        if request is not None:
            if request.client_revision > int(exam.configuration.get("last_client_revision", 0)):
                raise HTTPException(409, "pending client changes must be saved before submission")
            if any(
                exam.revisions.get(str(position), 0) < revision
                for position, revision in request.answer_revisions.items()
            ):
                raise HTTPException(409, "pending answers must be saved before submission")
        post_decision_exists = db.scalar(
            select(DecisionLog.id).where(
                DecisionLog.exam_id == exam.id,
                func.json_extract(DecisionLog.request, "$.event") == "post_exam",
            )
        )
        submit_exam(db, exam)
        if post_decision_exists is None and not any(item[0] == exam.template_id for item in CURATED_PACKS):
            await evaluate_and_log(
                "post_exam",
                db,
                exam_id=exam.id,
                extra_state={
                    "score": exam.score,
                    "correct_count": exam.correct_count,
                    "requested_template": exam.template_id,
                    "requested_difficulty": exam.configuration.get(
                        "requested_difficulty", "standard"
                    ),
                },
            )
        return _result_payload(db, exam)

    @app.get("/api/exams/{exam_id}/result")
    def result(exam_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        exam = get_exam(exam_id, db)
        if exam.result is None:
            raise HTTPException(409, "result is unavailable before submission")
        return _result_payload(db, exam)

    @app.get("/api/questions")
    def questions(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        q: str | None = Query(default=None, min_length=1, max_length=200),
        domain: str | None = None,
        topic: str | None = None,
        concept: str | None = None,
        difficulty: str | None = None,
        qtype: str | None = Query(None, alias="type"),
        verified: bool | None = None,
        bookmarked: bool | None = None,
        never_attempted: bool = False,
        wrong_before: bool = False,
        locale: Literal["zh-CN", "en-US"] = "zh-CN",
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        query = select(Question)
        for column, value in (
            (Question.domain, domain),
            (Question.topic, topic),
            (Question.concept, concept),
            (Question.difficulty, difficulty),
            (Question.type, qtype),
        ):
            if value is not None:
                query = query.where(column == value)
        if verified is not None:
            query = query.where(Question.verified == verified)
        if bookmarked is not None:
            query = query.where(Question.bookmarked == bookmarked)
        if never_attempted:
            query = query.where(~Question.id.in_(select(Attempt.question_id)))
        if wrong_before:
            query = query.where(
                Question.id.in_(select(Attempt.question_id).where(Attempt.is_correct.is_(False)))
            )
        if q is not None:
            escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            localized_prompt = func.json_extract(
                Question.payload, f'$.content_i18n."{locale}".prompt'
            )
            query = query.where(
                or_(
                    Question.id.ilike(pattern, escape="\\"),
                    Question.domain.ilike(pattern, escape="\\"),
                    Question.topic.ilike(pattern, escape="\\"),
                    Question.concept.ilike(pattern, escape="\\"),
                    localized_prompt.ilike(pattern, escape="\\"),
                )
            )
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.scalars(
            query.order_by(Question.id).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return {
            "items": [_bank_public(row, locale) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        }

    @app.get("/api/questions/{question_id}")
    def question_detail(
        question_id: str, locale: Literal["zh-CN", "en-US"] = "zh-CN", db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        question = db.get(Question, question_id)
        if question is None:
            raise HTTPException(404, "question not found")
        return _bank_public(question, locale)

    @app.put("/api/questions/{question_id}/bookmark")
    def bookmark(
        question_id: str, request: BookmarkRequest, db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        question = db.get(Question, question_id)
        if question is None:
            raise HTTPException(404, "question not found")
        question.bookmarked = request.bookmarked
        db.commit()
        return {"id": question_id, "bookmarked": request.bookmarked}

    def inspect_import(request: QuestionImportRequest, db: Session) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows, errors = parse_question_content(request.filename, request.content)
        # Detect boilerplate that only becomes visible when questions are reviewed as a pack.
        for locale in ("zh-CN", "en-US"):
            for field in ("explanation", "takeaway", "card.summary", "card.why_it_matters", "card.interview_angle", "card.common_pitfall"):
                occurrences: dict[str, list[int]] = {}
                for line, row in enumerate(rows, 1):
                    if not isinstance(row, dict):
                        continue
                    item = row.get("content_i18n", {}).get(locale, {})
                    text = item.get(field[5:]) if field.startswith("card.") else item.get(field)
                    if field.startswith("card.") and not isinstance(item.get("knowledge_card"), dict):
                        text = None
                    elif field.startswith("card."):
                        text = item["knowledge_card"].get(field[5:])
                    if isinstance(text, str) and text.strip():
                        occurrences.setdefault(text.strip().casefold(), []).append(line)
                for phrase, lines in occurrences.items():
                    if len(lines) >= max(5, int(len(rows) * 0.25)):
                        for line in lines:
                            field_name = field[5:] if field.startswith("card.") else field
                            errors.append({"line": line, "id": rows[line - 1].get("id"), "message": f"{locale} repeats the same {field_name} across the pack"})
        seen: set[str] = set(); duplicate_count = 0
        valid: list[dict[str, Any]] = []
        for line, row in enumerate(rows, 1):
            errors.extend(validate_candidate(row, line))
            if isinstance(row, dict) and row.get("id") in seen:
                errors.append({"line": line, "id": row.get("id"), "message": "duplicate id in upload"})
            elif isinstance(row, dict):
                seen.add(str(row.get("id"))); valid.append(row)
        existing = {row.id: row for row in db.scalars(select(Question).where(Question.id.in_(seen))).all()} if seen else {}
        importable: list[dict[str, Any]] = []
        for row in valid:
            prior = existing.get(row.get("id"))
            if prior is None: importable.append(row); continue
            promoted = {
                **row,
                "version": 2,
                "schema_version": 2,
                "verified": True,
                "selection_status": "active",
                "source_kind": row.get("source_kind", "imported"),
                "quality_tier": row.get("quality_tier", "imported_validated"),
            }
            if fingerprint(prior.payload) == fingerprint(promoted): duplicate_count += 1
            else: errors.append({"line": next(i for i, value in enumerate(rows, 1) if value is row), "id": row.get("id"), "message": "conflicting existing id"})
        report = {"valid_count": len(importable) if not errors else 0, "invalid_count": len(errors),
                  "duplicate_count": duplicate_count, "errors": errors}
        return importable, report

    @app.post("/api/questions/import/preview")
    def preview_question_import(request: QuestionImportRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
        _, report = inspect_import(request, db)
        return report

    @app.post("/api/questions/import")
    def import_questions(request: QuestionImportRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
        rows, report = inspect_import(request, db)
        if report["errors"]:
            conflict = any("conflicting existing id" in item["message"] for item in report["errors"])
            raise HTTPException(status_code=status.HTTP_409_CONFLICT if conflict else 422, detail=report)
        for row in rows:
            # Candidate uploads deliberately become local active inventory only after
            # full batch validation; the original content remains in payload.
            row = {
                **row,
                "version": 2,
                "schema_version": 2,
                "verified": True,
                "selection_status": "active",
                "source_kind": row.get("source_kind", "imported"),
                "quality_tier": row.get("quality_tier", "imported_validated"),
            }
            db.add(_question_row(row))
        db.commit()
        return {**report, "imported_count": len(rows), "skipped_count": report["duplicate_count"], "inserted": len(rows)}

    def review_items(mode: str, db: Session, locale: str) -> dict[str, Any]:
        if mode == "bookmarked":
            rows = db.scalars(
                select(Question).where(Question.bookmarked.is_(True)).order_by(Question.id)
            ).all()
        else:
            review_query = select(Question).join(
                ReviewQueue, ReviewQueue.question_id == Question.id
            )
            if mode == "due":
                review_query = review_query.where(ReviewQueue.due_at <= utcnow())
            rows = db.scalars(review_query.order_by(ReviewQueue.due_at)).all()
        return {"items": [_bank_public(row, locale) for row in rows]}

    @app.get("/api/review/wrong")
    def wrong(
        locale: Literal["zh-CN", "en-US"] = "zh-CN", db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        return review_items("wrong", db, locale)

    @app.get("/api/review/due")
    def due(
        locale: Literal["zh-CN", "en-US"] = "zh-CN", db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        return review_items("due", db, locale)

    @app.get("/api/review/bookmarked")
    def bookmarked_items(
        locale: Literal["zh-CN", "en-US"] = "zh-CN", db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        return review_items("bookmarked", db, locale)

    @app.post("/api/review/build-exam")
    def review_exam(request: ReviewBuildRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
        query = select(Question).where(Question.verified.is_(True))
        if request.mode == "bookmarked":
            query = query.where(Question.bookmarked.is_(True))
        else:
            query = query.join(ReviewQueue, ReviewQueue.question_id == Question.id)
            if request.mode == "due":
                query = query.where(ReviewQueue.due_at <= utcnow())
        return persist_exams(request, db, list(db.scalars(query).all()))

    @app.post("/api/drill/session")
    def create_drill(request: DrillRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
        query = select(Question).where(Question.verified.is_(True))
        if request.domain and request.domain != "mixed":
            query = query.where(Question.domain == request.domain)
        rows = list(db.scalars(query.order_by(Question.id)).all())
        quality = [row for row in rows if row.payload.get("selection_status") == "active" and row.payload.get("source_kind") in DRILL_SOURCE_KINDS]
        if not quality:
            raise HTTPException(409, "no modern interview questions available")
        attempted_ids = set(db.scalars(select(Attempt.question_id).distinct()))
        # Rapid practice means unseen content; targeted repetition lives in Review Queue.
        pool = [row for row in quality if row.id not in attempted_ids]
        if not pool:
            raise HTTPException(409, "no unseen eligible questions; use Review Queue for repetition")
        rows = pool
        rng = random.Random(uuid.uuid4().int)
        count = request.count or 160
        if count <= len(rows):
            shuffled = rows[:]; rng.shuffle(shuffled)
            selected_rows: list[Question] = []
            families: set[str] = set()
            for row in shuffled:
                family = str(row.family_id or row.id)
                if family not in families or len(rows) < count * 2:
                    selected_rows.append(row); families.add(family)
                if len(selected_rows) == count: break
            selected = [row.id for row in selected_rows]
        else:
            selected = [row.id for row in rows]
            rng.shuffle(selected)
            count = len(selected)
        drill = DrillSession(
            id=uuid.uuid4().hex, locale=request.locale, question_ids=selected, answers=[]
        )
        db.add(drill)
        db.commit()
        return {"id": drill.id, "count": count, "locale": request.locale}

    @app.get("/api/drill/{drill_id}/next")
    def drill_next(
        drill_id: str,
        locale: Literal["zh-CN", "en-US"] | None = None,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        drill = db.get(DrillSession, drill_id)
        if drill is None:
            raise HTTPException(404, "drill not found")
        if drill.status != "active" or drill.position >= len(drill.question_ids):
            raise HTTPException(409, "drill is complete")
        display_locale = locale or drill.locale
        question, payload = localized_drill_question(
            drill, drill.position + 1, display_locale, db
        )
        return _public_question(payload, drill.position + 1, question.bookmarked)

    @app.get("/api/drill/{drill_id}/question/{position}")
    def drill_question(
        drill_id: str,
        position: int,
        locale: Literal["zh-CN", "en-US"] | None = None,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        drill = db.get(DrillSession, drill_id)
        if drill is None:
            raise HTTPException(404, "drill not found")
        question, payload = localized_drill_question(drill, position, locale or drill.locale, db)
        return _public_question(payload, position, question.bookmarked)

    @app.get("/api/drill/{drill_id}/feedback/{position}")
    def drill_feedback(
        drill_id: str,
        position: int,
        locale: Literal["zh-CN", "en-US"] | None = None,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        drill = db.get(DrillSession, drill_id)
        if drill is None:
            raise HTTPException(404, "drill not found")
        if position < 1 or position > len(drill.answers):
            raise HTTPException(409, "feedback is not available for this position")
        entry = drill.answers[position - 1]
        question, _ = localized_drill_question(drill, position, locale or drill.locale, db)
        return localized_drill_feedback(question, entry, locale or drill.locale)

    @app.post("/api/drill/{drill_id}/answer")
    async def drill_answer(
        drill_id: str, request: DrillAnswerRequest, db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        drill = db.get(DrillSession, drill_id)
        if drill is None:
            raise HTTPException(404, "drill not found")
        if drill.status != "active" or drill.position >= len(drill.question_ids):
            raise HTTPException(409, "drill is complete")
        expected = drill.question_ids[drill.position]
        if request.question_id is not None and request.question_id != expected:
            raise HTTPException(409, "answer does not match current question")
        if request.position is not None and request.position != drill.position + 1:
            raise HTTPException(409, "answer does not match current position")
        question = db.get(Question, expected)
        if question is None:
            raise HTTPException(409, "question inventory changed")
        payload = question.payload
        normalized_answer = (
            request.answer
            if isinstance(request.answer, dict)
            else {"option_id": request.answer, "text": request.answer}
        )
        correct = grade_answer(payload, normalized_answer)
        entry = {
            "question_id": expected,
            "answer": normalized_answer,
            "is_correct": correct,
            "correct": correct,
        }
        drill.answers = [*drill.answers, entry]
        drill.position += 1
        db.add(
            Attempt(
                question_id=expected,
                exam_id=None,
                position=None,
                user_answer=normalized_answer,
                is_correct=correct,
            )
        )
        update_learning_state(db, payload, correct)
        db.commit()
        refreshed_by: str | None = None
        if drill.position % 10 == 0:
            decision = await evaluate_and_log(
                "rapid_refresh",
                db,
                extra_state={
                    "drill_id": drill.id,
                    "answered": drill.position,
                    "drill_accuracy": sum(item["is_correct"] for item in drill.answers)
                    / len(drill.answers),
                },
            )
            retarget_next_drill_block(db, drill, decision)
            refreshed_by = decision.provider
        return localized_drill_feedback(
            question, entry, request.locale or drill.locale, refreshed_by=refreshed_by
        )

    @app.post("/api/drill/{drill_id}/finish")
    def finish_drill(drill_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        drill = db.get(DrillSession, drill_id)
        if drill is None:
            raise HTTPException(404, "drill not found")
        drill.status = "finished"
        drill.finished_at = utcnow()
        db.commit()
        return {
            "id": drill.id,
            "answered": len(drill.answers),
            "correct": sum(item["is_correct"] for item in drill.answers),
            "status": "finished",
        }

    @app.get("/api/stats/dashboard")
    def dashboard(db: Session = Depends(get_db)) -> dict[str, Any]:
        start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today = db.scalars(select(Attempt).where(Attempt.attempted_at >= start)).all()
        all_attempts = db.scalars(select(Attempt)).all()
        target = int((db.get(Setting, "daily_target") or Setting(value="160", key="x")).value)
        completed = (
            db.scalar(
                select(func.count())
                .select_from(ExamSession)
                .where(and_(ExamSession.status == "submitted", ExamSession.finished_at >= start))
            )
            or 0
        )
        mastery_rows = db.scalars(select(ConceptMastery)).all()
        domain_totals: dict[str, tuple[int, int]] = {}
        for row in mastery_rows:
            attempts, correct = domain_totals.get(row.domain, (0, 0))
            domain_totals[row.domain] = (attempts + row.attempts, correct + row.correct)
        domain_mastery = {
            domain: correct / attempts if attempts else 0.0
            for domain, (attempts, correct) in domain_totals.items()
        }
        completed_today = db.scalars(
            select(ExamSession).where(
                and_(ExamSession.status == "submitted", ExamSession.finished_at >= start)
            )
        ).all()
        today_time_sec = sum(
            max(0, int((exam.finished_at - exam.started_at).total_seconds()))
            for exam in completed_today
            if exam.finished_at
        )
        return {
            "today_answered": len(today),
            "daily_target": target,
            "daily_goal": target,
            "today_accuracy": _accuracy(today),
            "today_papers": completed,
            "today_exams": completed,
            "total_answered": len(all_attempts),
            "overall_accuracy": _accuracy(all_attempts),
            "domain_mastery": {
                "sde": domain_mastery.get("sde", 0.0),
                "mle": domain_mastery.get("mle", 0.0),
            },
            "sde_mastery": domain_mastery.get("sde", 0.0),
            "mle_mastery": domain_mastery.get("mle", 0.0),
            "today_time_sec": today_time_sec,
            "today_seconds": today_time_sec,
            "review_due": db.scalar(
                select(func.count()).select_from(ReviewQueue).where(ReviewQueue.due_at <= utcnow())
            )
            or 0,
        }

    @app.get("/api/stats/topics")
    def topics_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
        rows = db.scalars(
            select(ConceptMastery).order_by(ConceptMastery.domain, ConceptMastery.concept)
        ).all()
        return {
            "items": [
                {
                    "id": f"{row.domain}:{row.concept}",
                    "domain": row.domain,
                    "concept": row.concept,
                    "topic": row.concept,
                    "attempts": row.attempts,
                    "answered": row.attempts,
                    "correct": row.correct,
                    "accuracy": row.correct / row.attempts if row.attempts else 0.0,
                    "recent_accuracy": row.weighted_mastery,
                    "wrong_count": row.attempts - row.correct,
                    "mastery": row.weighted_mastery,
                    "last_reviewed_at": row.last_seen_at.isoformat(),
                    "next_review_at": row.next_review_at.isoformat()
                    if row.next_review_at
                    else None,
                }
                for row in rows
            ]
        }

    @app.get("/api/stats/daily")
    def daily_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
        rows = db.execute(
            select(
                func.date(Attempt.attempted_at),
                func.count(),
                func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)),
            ).group_by(func.date(Attempt.attempted_at))
        ).all()
        return {
            "items": [
                {"date": date, "answered": count, "correct": int(correct or 0)}
                for date, count, correct in rows
            ]
        }

    @app.get("/api/stats/exams")
    def exam_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
        rows = db.scalars(
            select(ExamSession)
            .where(ExamSession.status == "submitted")
            .order_by(ExamSession.finished_at)
        ).all()
        return {"items": [_exam_summary(row) for row in rows]}

    @app.get("/api/settings")
    def settings(db: Session = Depends(get_db)) -> dict[str, Any]:
        locale = db.get(Setting, "locale")
        target = db.get(Setting, "daily_target")
        daily_target = int(target.value) if target else 160
        return {
            "locale": locale.value if locale else "zh-CN",
            "daily_target": daily_target,
        }

    @app.put("/api/settings")
    def update_settings(request: SettingsRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
        current_locale = db.get(Setting, "locale")
        current_target = db.get(Setting, "daily_target")
        normalized_locale = request.locale or (current_locale.value if current_locale else "zh-CN")
        normalized_target = (
            request.daily_target
            if request.daily_target is not None
            else int(current_target.value)
            if current_target
            else 160
        )
        values = {"locale": normalized_locale, "daily_target": str(normalized_target)}
        for key, value in values.items():
            row = db.get(Setting, key)
            if row is None:
                row = Setting(key=key, value=value)
                db.add(row)
            else:
                row.value = value
        db.commit()
        return {
            "locale": normalized_locale,
            "daily_target": normalized_target,
        }

    @app.get("/api/settings/provider/status")
    def provider_status(db: Session = Depends(get_db)) -> dict[str, Any]:
        last = db.scalar(select(DecisionLog).order_by(DecisionLog.id.desc()).limit(1))
        active = last.provider if last is not None else "rule-based"
        has_jev = bool(os.getenv("TYPESAFE_API_KEY"))
        return {
            "jev": (
                "connected"
                if active == "typesafe-jev"
                else "configured"
                if has_jev
                else "not_configured"
            ),
            "nanojev": "running" if active == "nanojev" else "offline",
            "von": "running" if active == "von" else "offline",
            "active_provider": active,
            "typesafe_jev": "configured" if has_jev else "not_configured",
            "last_checked_at": last.created_at.isoformat() if last is not None else None,
        }

    @app.post("/api/settings/provider/test")
    async def test_provider(db: Session = Depends(get_db)) -> dict[str, Any]:
        decision = await evaluate_and_log("manual_provider_test", db)
        return {"provider": decision.provider, "healthy": True}

    return app


def _exam_summary(exam: ExamSession) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "id": exam.id,
        "batch_id": exam.batch_id,
        "paper_index": exam.paper_index,
        "template_id": exam.template_id,
        "locale": exam.locale,
        "status": exam.status,
        "started_at": exam.started_at.isoformat(),
        "finished_at": exam.finished_at.isoformat() if exam.finished_at else None,
        "time_limit_sec": exam.time_limit_sec,
        "total_questions": len(exam.frozen_questions),
    }
    if exam.status == "submitted":
        summary["score"] = exam.score
        summary["correct_count"] = exam.correct_count
    return summary


def _exam_detail_payload(exam: ExamSession) -> dict[str, Any]:
    answers = {
        position: _display_answer(response)
        for position, response in exam.answers.items()
        if _display_answer(response) is not None
    }
    flags = sorted(int(position) for position, flagged in exam.flags.items() if flagged)
    return {
        **_exam_summary(exam),
        "duration_seconds": exam.time_limit_sec,
        "deadline_at": exam.deadline_at.isoformat(),
        "configuration": exam.configuration,
        "answers": answers,
        "answer_revisions": {
            int(position): revision for position, revision in exam.revisions.items()
        },
        "flags": flags,
        "questions": [
            {
                **_public_question(question, position),
                "response": exam.answers.get(str(position)),
                "revision": exam.revisions.get(str(position), 0),
                "flagged": exam.flags.get(str(position), False),
            }
            for position, question in enumerate(exam.frozen_questions, 1)
        ],
    }


def _display_answer(response: dict[str, Any] | None) -> str | None:
    if not response:
        return None
    for key in ("option_id", "text", "canonical"):
        value = response.get(key)
        if value is not None:
            return str(value)
    return None


def _result_payload(db: Session, exam: ExamSession) -> dict[str, Any]:
    if exam.result is None:
        raise HTTPException(409, "result is unavailable before submission")
    siblings: list[ExamSession] = []
    if exam.batch_id:
        siblings = list(
            db.scalars(
                select(ExamSession)
                .where(ExamSession.batch_id == exam.batch_id)
                .order_by(ExamSession.paper_index)
            ).all()
        )
    next_exam = next(
        (sibling for sibling in siblings if sibling.paper_index == exam.paper_index + 1),
        None,
    )
    return {
        **exam.result,
        "batch_id": exam.batch_id,
        "paper_index": exam.paper_index,
        "paper_count": len(siblings) if siblings else 1,
        "next_exam_id": next_exam.id if next_exam else None,
    }


def _accuracy(attempts: list[Attempt]) -> float:
    return sum(item.is_correct for item in attempts) / len(attempts) if attempts else 0.0


app = create_app()
