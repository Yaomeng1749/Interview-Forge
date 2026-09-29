from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any

from app.core.exam_builder import QUALITY_STYLES


def parse_question_content(filename: str, content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse JSON object/array or JSONL without ever partially accepting a batch."""
    errors: list[dict[str, Any]] = []
    try:
        if filename.lower().endswith(".jsonl"):
            rows = []
            for number, line in enumerate(content.splitlines(), 1):
                if line.strip():
                    try: rows.append(json.loads(line))
                    except json.JSONDecodeError as exc: errors.append({"line": number, "message": f"invalid JSON: {exc.msg}"})
        else:
            decoded = json.loads(content)
            rows = decoded if isinstance(decoded, list) else [decoded]
    except json.JSONDecodeError as exc:
        return [], [{"line": exc.lineno, "message": f"invalid JSON: {exc.msg}"}]
    if not isinstance(rows, list): return [], [{"line": 1, "message": "JSON must be an object or array"}]
    return rows, errors


def validate_candidate(row: Any, line: int) -> list[dict[str, Any]]:
    if not isinstance(row, dict): return [{"line": line, "message": "record must be an object"}]
    required = {"id", "domain", "topic", "concept", "question_family_id", "difficulty", "type", "content_i18n", "answer"}
    missing = sorted(required - set(row))
    errors = [{"line": line, "id": row.get("id"), "message": f"missing {field}"} for field in missing]
    if row.get("version", 2) < 2: errors.append({"line": line, "id": row.get("id"), "message": "imports require version 2"})
    if row.get("domain") not in {"sde", "mle"}: errors.append({"line": line, "id": row.get("id"), "message": "domain must be sde or mle"})
    if row.get("difficulty") not in {"L1", "L2", "L3"}: errors.append({"line": line, "id": row.get("id"), "message": "difficulty must be L1/L2/L3"})
    if row.get("type") not in {"single_choice", "fill_blank"}: errors.append({"line": line, "id": row.get("id"), "message": "unsupported type"})
    if row.get("question_style") not in QUALITY_STYLES: errors.append({"line": line, "id": row.get("id"), "message": "invalid question_style"})
    content = row.get("content_i18n", {})
    repeated_phrases = (
        "题目用于判断你能否根据约束选择合适的数据结构、算法和复杂度",
        "候选人能否识别合适的解决方案",
        "This question tests whether a candidate can identify the appropriate solution",
        "State the constraint first, then explain the mechanism, complexity, or trade-off",
        "Algorithms and data structures test whether you can choose mechanisms and complexity from constraints",
        "This matters in production systems and technical interviews",
        "This is a common interview topic",
        "并据此解释题设中观察到的现象",
        "该方案被作为题设场景的首要判断",
        "并将其视为题设中的主要处理机制",
        "treating it as the primary mechanism under the stated conditions",
        "using it to account for the observed behavior",
        "using it as the main explanation for the scenario",
    )
    for locale in ("zh-CN", "en-US"):
        item = content.get(locale) if isinstance(content, dict) else None
        if not isinstance(item, dict) or not all(item.get(key) for key in ("prompt", "explanation", "takeaway")):
            errors.append({"line": line, "id": row.get("id"), "message": f"{locale} requires prompt, explanation, takeaway"})
        elif not isinstance(item.get("knowledge_card"), dict):
            errors.append({"line": line, "id": row.get("id"), "message": f"{locale} requires knowledge_card"})
        if isinstance(item, dict):
            searchable = [item.get("prompt", ""), item.get("explanation", ""), item.get("takeaway", "")]
            card = item.get("knowledge_card")
            if isinstance(card, dict): searchable.extend(card.values())
            distractors = item.get("distractor_explanations")
            if isinstance(distractors, dict): searchable.extend(distractors.values())
            for phrase in repeated_phrases:
                if any(phrase.casefold() in str(value).casefold() for value in searchable):
                    errors.append({"line": line, "id": row.get("id"), "message": f"{locale} contains generic boilerplate: {phrase}"})
                    break
            for value in searchable:
                if isinstance(value, str) and re.search(r"\b(?:this question|本题|该题).{0,35}(?:tests?|考查).{0,45}(?:candidate|候选人).{0,30}(?:identify|识别).{0,30}(?:solution|方案)", value, re.I):
                    errors.append({"line": line, "id": row.get("id"), "message": f"{locale} contains templated explanation text"})
                    break
    if row.get("type") == "single_choice":
        answer_id = row.get("answer", {}).get("option_id") if isinstance(row.get("answer"), dict) else None
        for locale in ("zh-CN", "en-US"):
            item = content.get(locale, {}) if isinstance(content, dict) else {}
            options = item.get("options", []) if isinstance(item, dict) else []
            option_ids = [option.get("id") for option in options if isinstance(option, dict)]
            if len(options) != 4 or set(option_ids) != {"A", "B", "C", "D"}:
                errors.append({"line": line, "id": row.get("id"), "message": f"{locale} choice needs A-D options exactly once"})
                continue
            if answer_id not in option_ids:
                errors.append({"line": line, "id": row.get("id"), "message": "choice answer must name one A-D option"})
            texts = [str(option.get("text", "")).strip() for option in options]
            if len(set(text.casefold() for text in texts)) != 4:
                errors.append({"line": line, "id": row.get("id"), "message": f"{locale} options must be distinct"})
            distractors = item.get("distractor_explanations") if isinstance(item, dict) else None
            expected = set(option_ids) - {answer_id}
            if not isinstance(distractors, dict) or set(distractors) != expected:
                errors.append({"line": line, "id": row.get("id"), "message": f"{locale} needs a specific explanation for every distractor"})
            elif any("misses a constraint" in str(reason).lower() or "关键约束" in str(reason) for reason in distractors.values()):
                errors.append({"line": line, "id": row.get("id"), "message": f"{locale} distractor explanations cannot use a generic placeholder"})
            lengths = {option["id"]: len(str(option.get("text", "")).strip()) for option in options}
            if answer_id and lengths[answer_id] >= 15 and lengths[answer_id] > 1.5 * max(
                length for option_id, length in lengths.items() if option_id != answer_id
            ):
                errors.append({"line": line, "id": row.get("id"), "message": f"{locale} correct option is length-signaled; rewrite distractors to be comparably plausible"})
    return errors


def fingerprint(row: dict[str, Any]) -> str:
    return sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
