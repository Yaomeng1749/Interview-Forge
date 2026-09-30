from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.decision.base import DecisionResult
from app.decision.router import DecisionRouter
from app.models import Attempt, DecisionLog, DrillSession, ExamSession
from app.services import submit_exam


def test_health_templates_and_bilingual_settings(client: TestClient) -> None:
    assert client.get("/api/health").json()["question_bank"]["loaded"] == 40
    templates = client.get("/api/exam-templates").json()["items"]
    assert {item["id"] for item in templates} >= {"exam-a-sde", "exam-d-mle", "exam-g-mixed"}
    assert {item["id"] for item in templates if item.get("fixed_pack")} >= {
        "curated-a1-sde", "curated-d1-mle", "curated-g1-mixed", "curated-g2-mixed"
    }
    response = client.put("/api/settings", json={"locale": "en-US", "daily_target": 160})
    assert response.status_code == 200


def test_fixed_curated_exam_uses_manifest_and_localizes_pack(client: TestClient) -> None:
    import json

    from app.seed import import_bank

    project_root = Path(__file__).resolve().parents[2]
    pack_dir = project_root / "question_bank" / "curated_packs"
    with client.app.state.session_factory() as db:
        for pack in pack_dir.glob("paper_*.jsonl"):
            if pack.name != "paper_manifests.json":
                import_bank(db, pack)
    manifest = json.loads((pack_dir / "paper_manifests.json").read_text())
    expected = set(manifest["paper_G1_Mixed_standard_40"])
    built = client.post("/api/exams/build", json={
        "template_id": "curated-g1-mixed", "locale": "en-US", "seed": 17,
        "randomize_questions": False,
    })
    assert built.status_code == 200
    exam = client.get(f"/api/exams/{built.json()['id']}").json()
    assert {item["id"] for item in exam["questions"]} == expected
    assert all(item["locale"] == "en-US" and item["prompt"] for item in exam["questions"])
    assert sum(item["type"] == "single_choice" for item in exam["questions"]) == 30
    assert sum(item["type"] == "fill_blank" for item in exam["questions"]) == 10
    too_many = client.post("/api/exams/build", json={
        "template_id": "curated-g1-mixed", "paper_count": 4,
    })
    assert too_many.status_code == 422


def test_rapid_drill_samples_only_unseen_questions_and_shuffles(client: TestClient) -> None:
    import json

    from app.models import Attempt
    from app.seed import import_bank

    project_root = Path(__file__).resolve().parents[2]
    pack = project_root / "question_bank" / "curated_packs" / "paper_A1_SDE_standard_40.jsonl"
    with client.app.state.session_factory() as db:
        import_bank(db, pack)
        rows = [json.loads(line) for line in pack.read_text().splitlines()]
        for row in rows[:8]:
            db.add(Attempt(question_id=row["id"], exam_id=None, position=None, user_answer={}, is_correct=True))
        db.commit()
    manifest = json.loads((pack.parent / "paper_manifests.json").read_text())
    seen = set(manifest["paper_A1_SDE_standard_40"][:8])
    response = client.post("/api/drill/session", json={"count": 20, "domain": "sde"})
    assert response.status_code == 200
    with client.app.state.session_factory() as db:
        from app.models import DrillSession

        drill = db.get(DrillSession, response.json()["id"])
        selected = drill.question_ids
    assert len(selected) == 20
    assert not (set(selected) & seen)
    assert selected != manifest["paper_A1_SDE_standard_40"][:20]

def test_exam_in_progress_has_no_answer_leakage_and_revision_is_monotonic(
    client: TestClient,
) -> None:
    built = client.post(
        "/api/exams/build", json={"template_id": "exam-g-mixed", "locale": "zh-CN", "seed": 5}
    ).json()
    exam_id = built["exam_id"]
    exam = client.get(f"/api/exams/{exam_id}").json()
    serialized = str(exam).lower()
    assert all(
        term not in serialized for term in ("accepted_answers", "explanation", "correct_answer")
    )
    assert len(exam["questions"]) == 40

    saved = client.put(
        f"/api/exams/{exam_id}/answers/1", json={"revision": 2, "answer": {"option_id": "A"}}
    )
    stale = client.put(
        f"/api/exams/{exam_id}/answers/1", json={"revision": 1, "answer": {"option_id": "B"}}
    )
    assert saved.status_code == 200
    assert stale.status_code == 409
    assert (
        client.put(f"/api/exams/{exam_id}/flags/1", json={"flagged": True}).json()["flagged"]
        is True
    )


def test_submit_is_idempotent_and_unlocks_results(client: TestClient) -> None:
    exam_id = client.post(
        "/api/exams/build", json={"template_id": "exam-g-mixed", "locale": "en-US", "seed": 9}
    ).json()["exam_id"]
    before = client.get(f"/api/exams/{exam_id}/result")
    assert before.status_code == 409
    first = client.post(f"/api/exams/{exam_id}/submit").json()
    second = client.post(f"/api/exams/{exam_id}/submit").json()
    assert first == second
    assert first["score"] == 0 and first["total_questions"] == 40
    result = client.get(f"/api/exams/{exam_id}/result").json()
    assert result["questions"][0]["explanation"]
    assert len(client.get("/api/review/wrong").json()["items"]) == 40
    review_exam = client.post(
        "/api/review/build-exam",
        json={"mode": "wrong", "template_id": "exam-g-mixed", "locale": "en-US"},
    )
    assert review_exam.status_code == 200
    dashboard = client.get("/api/stats/dashboard").json()
    assert dashboard["total_answered"] == 40
    assert set(dashboard["domain_mastery"]) == {"sde", "mle"}


def test_submit_rejects_a_revision_that_has_not_been_saved(client: TestClient) -> None:
    exam_id = client.post(
        "/api/exams/build", json={"template_id": "exam-g-mixed", "locale": "en-US"}
    ).json()["exam_id"]
    pending = client.post(f"/api/exams/{exam_id}/submit", json={"client_revision": 1})
    assert pending.status_code == 409
    assert (
        client.put(
            f"/api/exams/{exam_id}/answers/1",
            json={"client_revision": 1, "answer": "A"},
        ).status_code
        == 200
    )
    assert (
        client.post(f"/api/exams/{exam_id}/submit", json={"client_revision": 1}).status_code == 200
    )


def test_flag_cannot_mask_two_restored_answers_that_still_need_sync(client: TestClient) -> None:
    exam_id = client.post(
        "/api/exams/build", json={"template_id": "exam-g-mixed", "locale": "en-US"}
    ).json()["exam_id"]
    assert (
        client.put(
            f"/api/exams/{exam_id}/flags/1",
            json={"flagged": True, "client_revision": 3},
        ).status_code
        == 200
    )
    pending = client.post(
        f"/api/exams/{exam_id}/submit",
        json={"client_revision": 2, "answer_revisions": {"1": 1, "2": 2}},
    )
    assert pending.status_code == 409
    assert (
        client.put(
            f"/api/exams/{exam_id}/answers/1", json={"client_revision": 1, "answer": "A"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/exams/{exam_id}/answers/2", json={"client_revision": 2, "answer": "A"}
        ).status_code
        == 200
    )
    result = client.post(
        f"/api/exams/{exam_id}/submit",
        json={"client_revision": 2, "answer_revisions": {"1": 1, "2": 2}},
    ).json()
    assert sum(item["user_answer"] is not None for item in result["questions"]) == 2


def test_submit_is_idempotent_for_two_preloaded_database_sessions(
    client: TestClient,
) -> None:
    exam_id = client.post(
        "/api/exams/build", json={"template_id": "exam-g-mixed", "locale": "en-US"}
    ).json()["exam_id"]
    session_factory = client.app.state.session_factory
    with session_factory() as first, session_factory() as stale:
        first_exam = first.get(ExamSession, exam_id)
        stale_exam = stale.get(ExamSession, exam_id)
        assert first_exam is not None and stale_exam is not None
        first_result = submit_exam(first, first_exam)
        stale_result = submit_exam(stale, stale_exam)
        assert stale_result == first_result
    with session_factory() as audit:
        attempt_count = audit.scalar(
            select(func.count()).select_from(Attempt).where(Attempt.exam_id == exam_id)
        )
        assert attempt_count == 40


def test_pagination_bookmarks_drill_and_stats_routes(client: TestClient) -> None:
    page = client.get("/api/questions?page=1&page_size=5&domain=sde").json()
    assert len(page["items"]) == 5 and page["page"] == 1 and page["total"] > 5
    question_id = page["items"][0]["id"]
    assert (
        client.put(f"/api/questions/{question_id}/bookmark", json={"bookmarked": True}).status_code
        == 200
    )
    assert client.get("/api/review/bookmarked").json()["items"][0]["id"] == question_id

    drill = client.post("/api/drill/session", json={"count": 20, "locale": "en-US"}).json()
    with client.app.state.session_factory() as audit:
        stored_drill = audit.get(DrillSession, drill["id"])
        assert stored_drill is not None
        assert len(set(stored_drill.question_ids)) == 20
    next_question = client.get(f"/api/drill/{drill['id']}/next").json()
    answered = client.post(
        f"/api/drill/{drill['id']}/answer",
        json={"question_id": next_question["id"], "answer": {"option_id": "__wrong__"}},
    ).json()
    assert "is_correct" in answered and "explanation" in answered
    assert answered["is_correct"] is False
    assert next_question["id"] in {
        item["id"] for item in client.get("/api/review/wrong").json()["items"]
    }
    assert any(
        item["concept"] == next_question["concept"]
        for item in client.get("/api/stats/topics").json()["items"]
    )
    assert client.post(f"/api/drill/{drill['id']}/finish").status_code == 200
    for route in ("dashboard", "topics", "daily", "exams"):
        assert client.get(f"/api/stats/{route}").status_code == 200


def test_drill_can_render_an_existing_session_in_the_requested_locale(client: TestClient) -> None:
    drill_id = client.post(
        "/api/drill/session", json={"count": 20, "locale": "zh-CN", "domain": "sde"}
    ).json()["id"]

    chinese = client.get(f"/api/drill/{drill_id}/next").json()
    english = client.get(f"/api/drill/{drill_id}/next?locale=en-US").json()

    assert chinese["locale"] == "zh-CN"
    assert english["locale"] == "en-US"
    assert chinese["id"] == english["id"]
    assert chinese["prompt"] != english["prompt"]


def test_drill_feedback_and_answered_question_relocalize(client: TestClient) -> None:
    drill_id = client.post(
        "/api/drill/session", json={"count": 20, "locale": "zh-CN", "domain": "mle"}
    ).json()["id"]
    current = client.get(f"/api/drill/{drill_id}/next").json()
    client.post(
        f"/api/drill/{drill_id}/answer",
        json={"position": current["position"], "answer": "__wrong__", "locale": "zh-CN"},
    )

    english_question = client.get(
        f"/api/drill/{drill_id}/question/{current['position']}?locale=en-US"
    ).json()
    english_feedback = client.get(
        f"/api/drill/{drill_id}/feedback/{current['position']}?locale=en-US"
    ).json()

    assert english_question["locale"] == "en-US"
    assert english_question["prompt"] != current["prompt"]
    assert english_feedback["locale"] == "en-US"
    assert english_feedback["explanation"]


def test_question_bank_search_matches_concept_and_localized_prompt(client: TestClient) -> None:
    first = client.get("/api/questions?page_size=1&locale=en-US").json()["items"][0]

    by_concept = client.get(
        "/api/questions",
        params={"q": first["concept"], "locale": "en-US", "page_size": 100},
    ).json()
    assert by_concept["total"] > 0
    assert all(
        first["concept"].casefold()
        in " ".join((item["id"], item["topic"], item["concept"], item["prompt"])).casefold()
        for item in by_concept["items"]
    )

    prompt_fragment = first["prompt"][:18]
    by_prompt = client.get(
        "/api/questions",
        params={"q": prompt_fragment, "locale": "en-US", "page_size": 100},
    ).json()
    assert first["id"] in {item["id"] for item in by_prompt["items"]}
    assert (
        client.get(
            "/api/questions",
            params={"q": "definitely-not-in-this-bank", "locale": "en-US"},
        ).json()["total"]
        == 0
    )


def test_batch_build_supports_four_papers_and_shortage_is_409(client: TestClient) -> None:
    response = client.post(
        "/api/exams/build",
        json={"template_id": "exam-g-mixed", "locale": "zh-CN", "paper_count": 4, "seed": 3},
    )
    assert response.status_code == 200
    exam_ids = response.json()["exam_ids"]
    assert len(exam_ids) == 4
    history = client.get("/api/exams/history").json()["items"]
    batch_statuses = {item["id"]: item["status"] for item in history if item["id"] in exam_ids}
    assert batch_statuses == {
        exam_ids[0]: "active",
        exam_ids[1]: "queued",
        exam_ids[2]: "queued",
        exam_ids[3]: "queued",
    }
    assert client.get(f"/api/exams/{exam_ids[1]}").status_code == 409
    first_result = client.post(f"/api/exams/{exam_ids[0]}/submit").json()
    assert first_result["batch_id"]
    assert first_result["paper_index"] == 1
    assert first_result["paper_count"] == 4
    assert first_result["next_exam_id"] == exam_ids[1]
    second = client.get(f"/api/exams/{exam_ids[1]}")
    assert second.status_code == 200
    assert second.json()["status"] == "active"
    assert (
        3595
        <= (
            datetime.fromisoformat(second.json()["deadline_at"])
            - datetime.fromisoformat(second.json()["started_at"])
        ).total_seconds()
        <= 3600
    )
    shortage = client.post(
        "/api/exams/build", json={"template_id": "exam-a-sde", "locale": "zh-CN"}
    )
    assert shortage.status_code == 409


def test_post_exam_decision_refreezes_next_paper_with_real_constraints(
    tmp_path: Path, monkeypatch
) -> None:
    production_bank = Path(__file__).resolve().parents[2] / "question_bank" / "questions.jsonl"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'adaptive.db'}")
    monkeypatch.setenv("QUESTION_BANK_PATH", str(production_bank))

    async def decide(_router: DecisionRouter, state: dict, _questions: dict) -> DecisionResult:
        if "score" in state:
            return DecisionResult(
                provider="test-jev",
                template_id="exam-a-sde",
                difficulty={"L1": 0, "L2": 0, "L3": 40},
                topic_weights={"backend_systems": 1.0},
            )
        return DecisionResult(provider="test-jev", template_id="exam-g-mixed")

    monkeypatch.setattr(DecisionRouter, "evaluate", decide)
    from app.main import create_app

    with TestClient(create_app()) as adaptive:
        built = adaptive.post(
            "/api/exams/build",
            json={
                "template_id": "exam-g-mixed",
                "locale": "en-US",
                "paper_count": 2,
                "seed": 17,
            },
        ).json()
        first_id, second_id = built["exam_ids"]
        adaptive.post(f"/api/exams/{first_id}/submit").raise_for_status()
        second = adaptive.get(f"/api/exams/{second_id}")
        second.raise_for_status()
        body = second.json()
        assert body["template_id"] == "exam-g-mixed"
        assert {question["domain"] for question in body["questions"]} == {"sde", "mle"}
        assert {question["difficulty"] for question in body["questions"]} == {"L3"}
        assert sum(question["topic"] == "backend_systems" for question in body["questions"]) == 20


def test_server_deadline_auto_submits(
    client: TestClient,
    monkeypatch,
) -> None:
    exam_id = client.post(
        "/api/exams/build",
        json={"template_id": "exam-g-mixed", "locale": "zh-CN", "seed": 33},
    ).json()["exam_id"]
    monkeypatch.setattr("app.main.utcnow", lambda: datetime.max)
    assert client.get(f"/api/exams/{exam_id}").json()["status"] == "submitted"


def test_missing_bank_is_reported_without_secret_or_crash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'empty.db'}")
    monkeypatch.setenv("QUESTION_BANK_PATH", str(tmp_path / "missing.jsonl"))
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-provider-key")
    from app.main import create_app

    with TestClient(create_app()) as isolated:
        health = isolated.get("/api/health").json()
        assert health["status"] == "degraded"
        assert health["question_bank"]["available"] is False
        assert isolated.post("/api/exams/build", json={}).status_code == 409
        body = str(isolated.get("/api/settings/provider/status").json())
        assert "test-provider-key" not in body


def test_browser_contract_supports_bilingual_full_exam_flow(client: TestClient) -> None:
    """The production React client and API must agree without test-only adapters."""
    templates = client.get("/api/exam-templates?locale=en-US").json()["items"]
    assert all(item["name"] and item["duration_minutes"] == 60 for item in templates)

    built = client.post(
        "/api/exams/build",
        json={
            "template_id": "exam-g-mixed",
            "locale": "en-US",
            "difficulty_preset": "standard",
            "timed": True,
            "allow_review": True,
            "randomize_questions": True,
            "randomize_options": True,
            "paper_count": 1,
            "seed": 91,
        },
    )
    assert built.status_code == 200
    exam_id = built.json()["id"]
    assert client.get("/api/exams/active").json()["id"] == exam_id

    exam = client.get(f"/api/exams/{exam_id}").json()
    assert exam["duration_seconds"] == 3600
    assert exam["answers"] == {}
    assert exam["flags"] == []
    first = exam["questions"][0]
    answer = "A" if first["type"] == "single_choice" else "0"
    saved = client.put(
        f"/api/exams/{exam_id}/answers/1",
        json={"client_revision": 1, "answer": answer},
    )
    assert saved.status_code == 200
    restored = client.get(f"/api/exams/{exam_id}").json()
    assert restored["answers"]["1"] == answer

    result = client.post(f"/api/exams/{exam_id}/submit", json={"client_revision": 1}).json()
    assert result["total_score"] == 100
    assert result["elapsed_seconds"] >= 0
    assert set(result) >= {
        "choice_accuracy",
        "fill_accuracy",
        "difficulty_breakdown",
        "topic_breakdown",
    }
    assert set(result["questions"][0]) >= {
        "prompt",
        "user_answer",
        "correct_answer",
        "correct",
        "explanation",
    }
    english_review = client.get("/api/review/wrong?locale=en-US").json()["items"]
    assert english_review
    assert all(item["prompt"].startswith("English question") for item in english_review)

    dashboard = client.get("/api/stats/dashboard").json()
    assert set(dashboard) >= {
        "today_exams",
        "today_seconds",
        "mle_mastery",
        "sde_mastery",
    }
    topics = client.get("/api/stats/topics").json()["items"]
    assert set(topics[0]) >= {
        "id",
        "topic",
        "answered",
        "accuracy",
        "recent_accuracy",
        "wrong_count",
        "last_reviewed_at",
    }


def test_configured_jev_is_not_reported_as_failed_before_first_decision(
    client: TestClient, monkeypatch,
) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-provider-key")
    status = client.get("/api/settings/provider/status")
    assert status.status_code == 200
    assert status.json()["jev"] == "configured"
    assert status.json()["active_provider"] == "rule-based"


def test_browser_contract_supports_settings_drill_and_provider_status(
    client: TestClient,
) -> None:
    saved = client.put("/api/settings", json={"locale": "en-US", "daily_goal": 200})
    assert saved.status_code == 200
    assert saved.json() == {"locale": "en-US", "daily_target": 200}

    status = client.get("/api/settings/provider/status").json()
    assert set(status) >= {"jev", "nanojev", "von", "active_provider"}
    assert "api_key" not in str(status).casefold()

    drill = client.post(
        "/api/drill/session",
        json={"count": 20, "locale": "en-US", "domain": "mixed"},
    )
    assert drill.status_code == 200
    drill_id = drill.json()["id"]
    question = client.get(f"/api/drill/{drill_id}/next").json()
    answer = "A" if question["type"] == "single_choice" else "0"
    feedback = client.post(
        f"/api/drill/{drill_id}/answer",
        json={"position": question["position"], "answer": answer},
    )
    assert feedback.status_code == 200
    assert isinstance(feedback.json()["correct"], bool)


def test_decision_provider_runs_before_and_after_exam_and_each_tenth_drill_answer(
    client: TestClient,
    monkeypatch,
) -> None:
    async def fake_evaluate(self, state, questions):  # type: ignore[no-untyped-def]
        del self, state, questions
        return DecisionResult(
            provider="nanojev",
            difficulty={"L1": 0, "L2": 0, "L3": 10},
            topic_weights={"data_structures_algorithms": 1.0},
        )

    monkeypatch.setattr(DecisionRouter, "evaluate", fake_evaluate)
    import json
    from app.seed import import_bank
    pack_dir = Path(__file__).resolve().parents[2] / "question_bank" / "curated_packs"
    with client.app.state.session_factory() as db:
        for pack in pack_dir.glob("paper_*.jsonl"):
            if pack.name != "paper_manifests.json":
                import_bank(db, pack)
    exam_id = client.post(
        "/api/exams/build", json={"template_id": "exam-g-mixed", "locale": "en-US"}
    ).json()["id"]
    assert client.post(f"/api/exams/{exam_id}/submit").status_code == 200

    drill_id = client.post("/api/drill/session", json={"count": 20, "locale": "en-US"}).json()["id"]
    with client.app.state.session_factory() as audit:
        original_next_block = list(audit.get(DrillSession, drill_id).question_ids[10:20])
    refresh = None
    for _ in range(10):
        question = client.get(f"/api/drill/{drill_id}/next").json()
        refresh = client.post(
            f"/api/drill/{drill_id}/answer",
            json={"position": question["position"], "answer": "__wrong__"},
        ).json()["decision_refresh"]
    assert refresh == "nanojev"
    with client.app.state.session_factory() as audit:
        adapted = audit.get(DrillSession, drill_id)
        assert adapted.question_ids[10:20] != original_next_block
        completed_ids = {row.question_id for row in audit.scalars(select(Attempt)).all()}
        assert len(adapted.question_ids) == len(set(adapted.question_ids))
        assert not (completed_ids & set(adapted.question_ids[10:20]))
        events = [
            row.request["event"]
            for row in audit.scalars(select(DecisionLog).order_by(DecisionLog.id)).all()
        ]
    assert {"pre_exam", "post_exam", "rapid_refresh"}.issubset(events)
    status = client.get("/api/settings/provider/status").json()
    assert status["active_provider"] == "nanojev"
    assert status["nanojev"] == "running"


def test_rapid_160_reaches_a_finished_summary(client: TestClient, monkeypatch) -> None:
    async def fast_rule(self, state, questions):  # type: ignore[no-untyped-def]
        del self, state, questions
        return DecisionResult(provider="rule-based")

    monkeypatch.setattr(DecisionRouter, "evaluate", fast_rule)
    from app.seed import import_bank
    pack_dir = Path(__file__).resolve().parents[2] / "question_bank" / "curated_packs"
    with client.app.state.session_factory() as db:
        for pack in pack_dir.glob("paper_*.jsonl"):
            if pack.name != "paper_manifests.json":
                import_bank(db, pack)
    drill_id = client.post("/api/drill/session", json={"count": 160, "locale": "en-US"}).json()[
        "id"
    ]
    for _ in range(160):
        question = client.get(f"/api/drill/{drill_id}/next").json()
        response = client.post(
            f"/api/drill/{drill_id}/answer",
            json={"position": question["position"], "answer": "__wrong__"},
        )
        assert response.status_code == 200
    assert client.get(f"/api/drill/{drill_id}/next").status_code == 409
    summary = client.post(f"/api/drill/{drill_id}/finish").json()
    assert summary == {
        "id": drill_id,
        "answered": 160,
        "correct": 0,
        "status": "finished",
    }
    assert client.get("/api/stats/dashboard").json()["total_answered"] == 160
