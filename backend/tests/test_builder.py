from collections import Counter
from pathlib import Path

import pytest

from app.core.exam_builder import (
    TEMPLATE_TOPIC_QUOTAS,
    InventoryShortage,
    build_standard_paper,
    load_questions,
)


def test_standard_builder_enforces_type_and_difficulty_invariants(bank_file: Path) -> None:
    questions = load_questions(bank_file)
    paper = build_standard_paper(questions, template_id="exam-g-mixed", locale="en-US", seed=7)
    assert len(paper) == 40
    assert sum(q["type"] == "single_choice" for q in paper) == 30
    assert sum(q["type"] == "fill_blank" for q in paper) == 10
    assert {
        level: sum(q["difficulty"] == level for q in paper) for level in ("L1", "L2", "L3")
    } == {"L1": 12, "L2": 20, "L3": 8}
    assert all(q["locale"] == "en-US" for q in paper)


def test_builder_is_deterministic_and_fails_closed_on_shortage(bank_file: Path) -> None:
    questions = load_questions(bank_file)
    first = build_standard_paper(questions, template_id="exam-g-mixed", locale="zh-CN", seed=123)
    second = build_standard_paper(questions, template_id="exam-g-mixed", locale="zh-CN", seed=123)
    assert [q["id"] for q in first] == [q["id"] for q in second]
    with pytest.raises(InventoryShortage):
        build_standard_paper(questions[:39], template_id="exam-g-mixed", locale="zh-CN", seed=1)


@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        ("foundation", {"L1": 20, "L2": 16, "L3": 4}),
        ("standard", {"L1": 12, "L2": 20, "L3": 8}),
        ("intensive", {"L1": 6, "L2": 20, "L3": 14}),
        ("hard", {"L1": 2, "L2": 14, "L3": 24}),
    ],
)
def test_builder_supports_all_documented_difficulty_presets(
    bank_file: Path, preset: str, expected: dict[str, int]
) -> None:
    questions = load_questions(bank_file)
    # Repeat the fixture to make every preset cell sufficiently large while
    # preserving unique IDs, then verify the final paper rather than config only.
    expanded = []
    for copy_index in range(4):
        for question in questions:
            clone = {**question, "id": f"{question['id']}-copy-{copy_index}"}
            expanded.append(clone)
    paper = build_standard_paper(
        expanded,
        template_id="exam-g-mixed",
        locale="en-US",
        seed=7,
        difficulty_preset=preset,
    )
    assert {level: sum(q["difficulty"] == level for q in paper) for level in expected} == expected
    assert sum(q["type"] == "single_choice" for q in paper) == 30
    assert sum(q["type"] == "fill_blank" for q in paper) == 10


@pytest.mark.parametrize("template_id", ["exam-a-sde", "exam-d-mle", "exam-g-mixed"])
def test_production_bank_enforces_standard_topic_blueprints(template_id: str) -> None:
    bank = Path(__file__).resolve().parents[2] / "question_bank" / "questions.jsonl"
    paper = build_standard_paper(load_questions(bank), template_id, locale="en-US", seed=20260921)
    assert Counter(question["topic"] for question in paper) == Counter(
        TEMPLATE_TOPIC_QUOTAS[template_id]
    )
    assert len({question["id"] for question in paper}) == 40


def test_adaptive_constraints_change_real_difficulty_and_topic_distribution() -> None:
    bank = Path(__file__).resolve().parents[2] / "question_bank" / "questions.jsonl"
    paper = build_standard_paper(
        load_questions(bank),
        "exam-a-sde",
        locale="en-US",
        seed=1,
        difficulty_quotas={"L1": 0, "L2": 0, "L3": 40},
        topic_weights={"backend_systems": 1.0},
    )
    assert Counter(question["difficulty"] for question in paper) == {"L3": 40}
    assert Counter(question["type"] for question in paper) == {
        "single_choice": 30,
        "fill_blank": 10,
    }
    assert Counter(question["topic"] for question in paper) == {"backend_systems": 40}
