from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from sqlalchemy import func, select

from app.core.exam_builder import build_standard_paper
from app.models import Attempt, Question
from app.seed import import_bank


def _curated(index: int, *, domain: str, difficulty: str, style: str) -> dict:
    qtype = "fill_blank" if index % 4 == 0 else "single_choice"
    content = {
        "prompt": f"Question {index}: choose the production-safe design.",
        "options": ([{"id": key, "text": f"Option {key}"} for key in "ABCD"] if qtype == "single_choice" else []),
        "explanation": "The answer follows the stated system constraint.",
        "distractor_explanations": {key: "It violates the stated production invariant." for key in "BCD"},
        "takeaway": "State the invariant before choosing a design.",
        "knowledge_card": {"summary": "A durable interview concept.", "why_it_matters": "It changes correctness.", "interview_angle": "Explain the trade-off.", "common_pitfall": "Optimizing the wrong constraint."},
    }
    return {
        "id": f"{domain}-quality-{index:04d}", "domain": domain,
        "topic": f"{domain}_topic_{index % 5}", "concept": f"{domain}_concept_{index}",
        "question_family_id": f"quality-family-{index}", "difficulty": difficulty,
        "type": qtype, "content_i18n": {"zh-CN": content, "en-US": content},
        "answer": {"option_id": "A"} if qtype == "single_choice" else {"text": "invariant"},
        "accepted_answers": [] if qtype == "single_choice" else ["invariant"],
        "regex_answers": [], "numeric_answer": None, "numeric_tolerance": None, "parameters": {},
        "verified": True, "verification": {"method": "stable_fact", "solver": "", "solver_version": "v3", "evidence": "test"}, "version": 2,
        "schema_version": 2, "source_kind": "curated", "quality_tier": "curated",
        "selection_status": "active", "question_style": style, "cognitive_skill": "analyze",
        "knowledge_points": [f"{domain}_concept_{index}"], "tags": ["interview"], "source_refs": [],
    }


def test_curated_paper_enforces_quality_mix() -> None:
    questions = [
        _curated(i, domain="sde" if i % 2 else "mle", difficulty=("L3" if i < 32 else "L2"), style=("calculation" if i < 2 else ["concept", "scenario", "code_reasoning", "debugging", "system_design", "tradeoff"][i % 6]))
        for i in range(80)
    ]
    paper = build_standard_paper(questions, "exam-g-mixed", "en-US", 11, "intensive")
    assert len(paper) == 40
    assert len({item["id"] for item in paper}) == 40
    assert len({item["question_family_id"] for item in paper}) == 40
    assert sum(item.get("question_style") == "calculation" for item in paper) <= 6
    assert len({item.get("question_style") for item in paper}) >= 5
    assert sum(item["difficulty"] == "L1" for item in paper) <= 6
    assert sum(item["difficulty"] == "L3" for item in paper) >= 14


def test_incremental_seed_adds_only_missing_ids(tmp_path) -> None:
    from app.database import create_database, run_migrations
    import os
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'seed.db'}"
    engine, factory = create_database(); run_migrations(engine)
    rows = [_curated(i, domain="sde", difficulty="L3", style="concept") for i in range(2)]
    bank = tmp_path / "bank.jsonl"; bank.write_text("\n".join(json.dumps(row) for row in rows))
    with factory() as db:
        assert import_bank(db, bank)["inserted"] == 2
        db.add(Attempt(question_id=rows[0]["id"], exam_id=None, position=None, user_answer={}, is_correct=True)); db.commit()
        assert import_bank(db, bank)["inserted"] == 0
        assert db.scalar(select(func.count()).select_from(Attempt)) == 1


def test_import_endpoint_is_atomic_and_promotes_candidate(client) -> None:
    row = _curated(900, domain="mle", difficulty="L3", style="scenario")
    row["verified"] = False; row["selection_status"] = "candidate"
    bad = dict(row); bad["id"] = "mle-quality-0901"; bad.pop("content_i18n")
    response = client.post("/api/questions/import", json={"filename": "x.jsonl", "content": "\n".join(json.dumps(x) for x in (row, bad))})
    assert response.status_code == 422
    assert client.get(f"/api/questions/{row['id']}").status_code == 404
    response = client.post("/api/questions/import", json={"filename": "x.jsonl", "content": json.dumps(row)})
    assert response.status_code == 200
    assert response.json()["inserted"] == 1


def test_import_rejects_length_signaled_or_generic_choice_distractors(client) -> None:
    row = _curated(902, domain="mle", difficulty="L2", style="scenario")
    row["content_i18n"]["en-US"]["options"][0]["text"] = "A" * 80
    row["answer"] = {"option_id": "A"}
    response = client.post("/api/questions/import", json={"filename": "bad.json", "content": json.dumps(row)})
    assert response.status_code == 422
    assert "length-signaled" in str(response.json())


def test_import_rejects_a_pack_full_of_repeated_explanations(client) -> None:
    rows = [_curated(920 + i, domain="mle", difficulty="L2", style="scenario") for i in range(8)]
    response = client.post("/api/questions/import/preview", json={
        "filename": "boilerplate.jsonl",
        "content": "\n".join(json.dumps(row) for row in rows),
    })
    assert response.status_code == 200
    assert response.json()["invalid_count"] > 0
    assert "repeats the same explanation" in str(response.json())


def test_cleanup_keeps_attempted_legacy_and_finishes_affected_drill(tmp_path) -> None:
    from app.database import create_database, run_migrations
    from app.models import DrillSession
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'cleanup.db'}"
    engine, factory = create_database(); run_migrations(engine)
    old = _curated(1, domain="sde", difficulty="L3", style="concept"); old["id"] = "sde-legacy-old-0001"; old["version"] = 1; old.pop("selection_status")
    used = dict(old); used["id"] = "sde-legacy-used-0002"
    curated = [_curated(i + 1000, domain="mle", difficulty="L3", style="scenario") for i in range(120)]
    with factory() as db:
        for row in [old, used, *curated]: db.add(Question(id=row["id"], domain=row["domain"], topic=row["topic"], concept=row["concept"], family_id=row["question_family_id"], difficulty=row["difficulty"], type=row["type"], verified=True, version=row["version"], payload=row))
        db.flush()
        db.add(Attempt(question_id=used["id"], exam_id=None, position=None, user_answer={}, is_correct=True))
        db.add(DrillSession(id="affected", locale="en-US", question_ids=[old["id"]], answers=[]))
        db.commit()
    script = __import__("pathlib").Path(__file__).resolve().parents[2] / "scripts" / "cleanup_unattempted_legacy_questions.py"
    result = subprocess.run([sys.executable, str(script), "--apply"], env={**os.environ, "PYTHONPATH": str(script.parents[1])}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with factory() as db:
        assert db.get(Question, old["id"]) is None
        assert db.get(Question, used["id"]) is not None
        assert db.scalar(select(func.count()).select_from(Attempt)) == 1
        assert db.get(DrillSession, "affected").status == "finished"


def test_purge_removes_all_legacy_questions_and_their_attempts(tmp_path) -> None:
    from app.database import create_database, run_migrations
    from app.models import DrillSession, ReviewQueue

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'purge.db'}"
    engine, factory = create_database(); run_migrations(engine)
    legacy = _curated(1, domain="sde", difficulty="L1", style="calculation")
    legacy["id"] = "sde-legacy-calculation-0001"; legacy["version"] = 1; legacy.pop("selection_status")
    curated = _curated(1000, domain="mle", difficulty="L3", style="scenario")
    with factory() as db:
        for row in (legacy, curated):
            db.add(Question(id=row["id"], domain=row["domain"], topic=row["topic"], concept=row["concept"], family_id=row["question_family_id"], difficulty=row["difficulty"], type=row["type"], verified=True, version=row["version"], payload=row))
        db.flush()
        db.add(Attempt(question_id=legacy["id"], exam_id=None, position=None, user_answer={}, is_correct=False))
        db.add(ReviewQueue(question_id=legacy["id"], reason="wrong_answer"))
        db.add(DrillSession(id="legacy-drill", locale="zh-CN", question_ids=[legacy["id"]], answers=[]))
        db.commit()
    script = __import__("pathlib").Path(__file__).resolve().parents[2] / "scripts" / "purge_legacy_questions.py"
    result = subprocess.run([sys.executable, str(script), "--apply"], env={**os.environ, "PYTHONPATH": str(script.parents[1])}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with factory() as db:
        assert db.get(Question, legacy["id"]) is None
        assert db.get(Question, curated["id"]) is not None
        assert db.scalar(select(func.count()).select_from(Attempt)) == 0
        assert db.get(DrillSession, "legacy-drill") is None
