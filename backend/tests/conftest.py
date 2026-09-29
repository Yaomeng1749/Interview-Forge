from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def make_question(index: int, qtype: str, difficulty: str, domain: str = "sde") -> dict:
    qid = f"{domain}-{qtype}-{difficulty}-{index:04d}"
    localized = {
        "zh-CN": {
            "prompt": f"中文题目 {qid}",
            "options": (
                [{"id": "A", "text": "正确"}, {"id": "B", "text": "错误"}]
                if qtype == "single_choice"
                else []
            ),
            "explanation": "中文解析",
            "distractor_explanations": {"B": "错误原因"},
            "takeaway": "中文知识点总结",
            "knowledge_card": {"summary": "中文核心概念"},
        },
        "en-US": {
            "prompt": f"English question {qid}",
            "options": (
                [{"id": "A", "text": "Correct"}, {"id": "B", "text": "Wrong"}]
                if qtype == "single_choice"
                else []
            ),
            "explanation": "English explanation",
            "distractor_explanations": {"B": "Why it is wrong"},
            "takeaway": "English takeaway",
            "knowledge_card": {"summary": "English core concept"},
        },
    }
    return {
        "id": qid,
        "domain": domain,
        "topic": "algorithms" if domain == "sde" else "machine_learning",
        "concept": f"concept_{index % 5}",
        "question_family_id": f"family_{index}",
        "difficulty": difficulty,
        "type": qtype,
        "content_i18n": localized,
        "answer": {"option_id": "A"} if qtype == "single_choice" else {"text": "Backpropagation"},
        "accepted_answers": []
        if qtype == "single_choice"
        else ["backpropagation", "backprop", "反向传播"],
        "regex_answers": [] if qtype == "single_choice" else ["^back[- ]?propagation$"],
        "numeric_answer": None,
        "numeric_tolerance": None,
        "verification": {"method": "test", "evidence": "fixture"},
        "verified": True,
        "version": 2,
        "schema_version": 2,
        "source_kind": "curated",
        "selection_status": "active",
        "quality_tier": "curated",
        "question_style": ["scenario", "concept", "tradeoff", "debugging", "system_design"][index % 5],
    }


@pytest.fixture()
def bank_file(tmp_path: Path) -> Path:
    rows: list[dict] = []
    # Enough inventory by both type and exact standard difficulty totals.
    for difficulty, count in (("L1", 12), ("L2", 20), ("L3", 8)):
        fill_count = {"L1": 3, "L2": 5, "L3": 2}[difficulty]
        for i in range(count):
            rows.append(
                make_question(
                    i,
                    "fill_blank" if i < fill_count else "single_choice",
                    difficulty,
                    "sde" if i % 2 == 0 else "mle",
                )
            )
    path = tmp_path / "questions.jsonl"
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8"
    )
    return path


@pytest.fixture()
def client(tmp_path: Path, bank_file: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'trainer.db'}")
    monkeypatch.setenv("QUESTION_BANK_PATH", str(bank_file))
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"
