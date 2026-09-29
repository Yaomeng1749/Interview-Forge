from app.core.grading import grade_answer, normalize_text


def test_normalize_text_handles_unicode_case_and_whitespace() -> None:
    assert normalize_text("  ＢＡＣＫＰＲＯＰ  ") == "backprop"


def test_choice_grading_is_exact() -> None:
    question = {"type": "single_choice", "answer": {"option_id": "A"}}
    assert grade_answer(question, {"option_id": "A"}) is True
    assert grade_answer(question, {"option_id": "B"}) is False


def test_fill_grading_supports_alias_regex_and_numeric_tolerance() -> None:
    aliases = {"type": "fill_blank", "accepted_answers": ["backprop", "反向传播"]}
    regex = {"type": "fill_blank", "accepted_answers": [], "regex_answers": [r"^o\(log n\)$"]}
    numeric = {
        "type": "fill_blank",
        "accepted_answers": [],
        "numeric_answer": 3.14,
        "numeric_tolerance": 0.01,
    }
    assert grade_answer(aliases, {"text": " BackProp "}) is True
    assert grade_answer(regex, {"text": "O(log n)"}) is True
    assert grade_answer(numeric, {"text": "3.145"}) is True
    assert grade_answer(numeric, {"text": "3.2"}) is False
