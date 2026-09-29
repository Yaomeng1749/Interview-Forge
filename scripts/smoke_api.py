#!/usr/bin/env python3
"""Run a dependency-free live API smoke against an already running backend."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any


def request(base: str, path: str, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    health = request(base, "/api/health")
    assert health["status"] == "ok" and health["question_bank"]["loaded"] == 1000
    built = request(
        base,
        "/api/exams/build",
        "POST",
        {
            "template_id": "exam-g-mixed",
            "locale": "en-US",
            "difficulty_preset": "standard",
            "paper_count": 4,
            "seed": 20260921,
            "randomize_options": True,
        },
    )
    exam_id = built["id"]
    assert len(built["exam_ids"]) == 4
    history = request(base, "/api/exams/history")["items"]
    batch_status = {
        item["id"]: item["status"] for item in history if item["id"] in built["exam_ids"]
    }
    assert batch_status[built["exam_ids"][0]] == "active"
    assert all(batch_status[item] == "queued" for item in built["exam_ids"][1:])
    exam = request(base, f"/api/exams/{urllib.parse.quote(exam_id)}")
    questions = exam["questions"]
    assert len(questions) == 40
    assert Counter(q["type"] for q in questions) == {"single_choice": 30, "fill_blank": 10}
    assert Counter(q["difficulty"] for q in questions) == {"L1": 12, "L2": 20, "L3": 8}
    assert Counter(q["domain"] for q in questions) == {"sde": 20, "mle": 20}
    assert Counter(q["topic"] for q in questions) == {
        "data_structures_algorithms": 6,
        "operating_systems": 3,
        "networks": 2,
        "databases": 3,
        "backend_systems": 6,
        "math_statistics": 2,
        "classical_ml": 3,
        "mlops_evaluation": 2,
        "deep_learning": 3,
        "pytorch_training": 2,
        "transformer_llm": 5,
        "ml_systems_inference": 3,
    }
    serialized = json.dumps(exam).casefold()
    for forbidden in ("accepted_answers", "correct_answer", "explanation", "verification"):
        assert forbidden not in serialized

    first = questions[0]
    answer = first["options"][0]["id"] if first["type"] == "single_choice" else "0"
    request(
        base,
        f"/api/exams/{exam_id}/answers/1",
        "PUT",
        {"client_revision": 1, "answer": answer},
    )
    restored = request(base, f"/api/exams/{exam_id}")
    assert restored["answers"]["1"] == answer
    result = request(base, f"/api/exams/{exam_id}/submit", "POST", {"client_revision": 1})
    assert result["total_score"] == 100 and len(result["questions"]) == 40
    assert result["questions"][0]["explanation"]
    assert result["next_exam_id"] == built["exam_ids"][1]
    second = request(base, f"/api/exams/{built['exam_ids'][1]}")
    assert second["status"] == "active"
    assert request(
        base,
        "/api/questions?locale=en-US&q=definitely-not-in-this-bank",
    )["total"] == 0
    assert request(base, "/api/exam-templates?locale=en-US")["items"][0]["name"].startswith("SDE")
    assert request(base, "/api/settings/provider/status")["active_provider"] == "rule-based"
    assert request(
        base, "/api/drill/session", "POST", {"count": 160, "locale": "en-US"}
    )["count"] == 160
    print("PASS: live bilingual API, blueprint, queued batch, search, provider, and drill flow")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, urllib.error.URLError) as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
