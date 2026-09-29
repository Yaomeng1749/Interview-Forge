from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_text(value: str) -> str:
    """Normalize without applying fuzzy or semantic matching."""
    return unicodedata.normalize("NFKC", value).strip().casefold()


def grade_answer(question: dict[str, Any], response: dict[str, Any] | None) -> bool:
    if not response:
        return False
    if question["type"] == "single_choice":
        return response.get("option_id") == question.get("answer", {}).get("option_id")

    raw = str(response.get("text", ""))
    value = normalize_text(raw)
    if not value:
        return False
    if value in {normalize_text(str(item)) for item in question.get("accepted_answers", [])}:
        return True
    for pattern in question.get("regex_answers", []):
        if re.fullmatch(pattern, value, flags=re.IGNORECASE):
            return True
    numeric_answer = question.get("numeric_answer")
    if numeric_answer is not None:
        try:
            tolerance = float(question.get("numeric_tolerance") or 0)
            return abs(float(value) - float(numeric_answer)) <= tolerance
        except ValueError:
            return False
    canonical = question.get("answer", {}).get("text")
    return canonical is not None and value == normalize_text(str(canonical))
