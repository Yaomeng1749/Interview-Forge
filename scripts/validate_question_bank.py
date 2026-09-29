#!/usr/bin/env python3
"""Dependency-free validation for the bilingual seed question bank."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


LOCALES = ("zh-CN", "en-US")
DOMAINS = ("sde", "mle")
DIFFICULTIES = ("L1", "L2", "L3")
QUESTION_TYPES = ("single_choice", "fill_blank")
EXPECTED_COUNTS = {
    "total": 1000,
    "domain": {"sde": 500, "mle": 500},
    "type": {"single_choice": 740, "fill_blank": 260},
    "difficulty": {"L1": 300, "L2": 500, "L3": 200},
    "domain_type_difficulty": {
        domain: {
            "single_choice": {"L1": 110, "L2": 185, "L3": 75},
            "fill_blank": {"L1": 40, "L2": 65, "L3": 25},
        }
        for domain in DOMAINS
    },
}
REQUIRED_FIELDS = {
    "id",
    "domain",
    "topic",
    "concept",
    "question_family_id",
    "difficulty",
    "type",
    "content_i18n",
    "answer",
    "accepted_answers",
    "regex_answers",
    "numeric_answer",
    "numeric_tolerance",
    "parameters",
    "verified",
    "verification",
    "version",
}
ID_PATTERN = re.compile(r"^(?:sde|mle)-[a-z0-9]+(?:-[a-z0-9]+)*-[0-9]{4}$")
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "question_bank" / "schema.json"


def canonical_prompt_fingerprint(prompt: str) -> str:
    normalized = unicodedata.normalize("NFKC", prompt).casefold()
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _type_matches(value: Any, expected: str) -> bool:
    """Return JSON-type compatibility without treating booleans as numbers."""
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def _resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported schema reference {ref!r}")
    node: Any = root_schema
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(node, dict):
        raise ValueError(f"schema reference {ref!r} is not an object")
    return node


def _schema_errors(
    value: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str = "$",
) -> list[str]:
    """Execute the JSON-Schema keywords used by the checked-in draft-2020 schema.

    Keeping this small executor in-tree makes the bank verifier dependency-free while
    still ensuring the published schema is applied to every record rather than merely
    checking that a schema file exists.
    """
    if "$ref" in schema:
        return _schema_errors(
            value,
            _resolve_ref(root_schema, schema["$ref"]),
            root_schema=root_schema,
            path=path,
        )

    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else expected
        if not isinstance(expected_types, list) or not any(
            isinstance(item, str) and _type_matches(value, item)
            for item in expected_types
        ):
            return [f"{path}: schema type expected {expected!r}"]

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: schema const expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: schema enum rejected {value!r}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: schema required property missing")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key}: schema additionalProperties rejected unexpected field")
        for key, child_schema in properties.items():
            if key in value and isinstance(child_schema, dict):
                errors.extend(
                    _schema_errors(
                        value[key],
                        child_schema,
                        root_schema=root_schema,
                        path=f"{path}.{key}",
                    )
                )

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: schema minItems={schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: schema maxItems={schema['maxItems']}")
        if schema.get("uniqueItems"):
            rendered = [
                json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                for item in value
            ]
            if len(rendered) != len(set(rendered)):
                errors.append(f"{path}: schema uniqueItems violation")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _schema_errors(
                        item,
                        item_schema,
                        root_schema=root_schema,
                        path=f"{path}[{index}]",
                    )
                )

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: schema minLength={schema['minLength']}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            errors.append(f"{path}: schema pattern mismatch")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: schema minimum={schema['minimum']}")
    return errors


def validate_with_schema(question: dict[str, Any]) -> list[str]:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"schema.json unreadable: {exc}"]
    try:
        return _schema_errors(question, schema, root_schema=schema)
    except (KeyError, TypeError, ValueError) as exc:
        return [f"schema.json execution failed: {exc}"]


def validate_question(question: dict[str, Any]) -> list[str]:
    errors: list[str] = validate_with_schema(question)
    question_id = question.get("id", "<missing-id>")
    missing = sorted(REQUIRED_FIELDS - set(question))
    if missing:
        errors.append(f"{question_id}: schema missing required fields: {missing}")
        return errors

    if not isinstance(question_id, str) or not ID_PATTERN.fullmatch(question_id):
        errors.append(f"{question_id}: schema invalid id")
    domain = question.get("domain")
    if domain not in DOMAINS:
        errors.append(f"{question_id}: schema invalid domain {domain!r}")
    elif isinstance(question_id, str) and not question_id.startswith(f"{domain}-"):
        errors.append(f"{question_id}: id/domain mismatch")
    if question.get("difficulty") not in DIFFICULTIES:
        errors.append(f"{question_id}: schema invalid difficulty")
    question_type = question.get("type")
    if question_type not in QUESTION_TYPES:
        errors.append(f"{question_id}: schema invalid type")
    for key in ("topic", "concept", "question_family_id"):
        if not _nonempty_string(question.get(key)):
            errors.append(f"{question_id}: schema {key} must be non-empty")
    if question.get("verified") is not True:
        errors.append(f"{question_id}: verified must be true for seed inventory")
    if question.get("version") != 1:
        errors.append(f"{question_id}: version must equal 1")
    if not isinstance(question.get("parameters"), dict):
        errors.append(f"{question_id}: parameters must be an object")

    verification = question.get("verification")
    if not isinstance(verification, dict):
        errors.append(f"{question_id}: verification must be an object")
    else:
        if verification.get("method") not in {"reference_solver", "stable_fact"}:
            errors.append(f"{question_id}: unsupported verification.method")
        if not _nonempty_string(verification.get("evidence")):
            errors.append(f"{question_id}: verification.evidence must be non-empty")

    # Solver-backed records are independently recomputed during validation.  The
    # import is lazy so this validator remains usable for hand-authored stable facts.
    if isinstance(verification, dict) and _nonempty_string(verification.get("solver")):
        try:
            try:
                from scripts.generate_question_bank import format_fraction, solve
            except ModuleNotFoundError:
                from generate_question_bank import format_fraction, solve
            expected_answer = format_fraction(
                solve(verification["solver"], question.get("parameters", {}))
            )
            if question.get("type") == "single_choice":
                answer_id = question.get("answer", {}).get("option_id")
                observed: set[str] = set()
                for locale in LOCALES:
                    for option in question.get("content_i18n", {}).get(locale, {}).get("options", []):
                        if option.get("id") == answer_id:
                            match = re.match(r"^-?\d+(?:\.\d+)?", str(option.get("text", "")))
                            if match:
                                observed.add(match.group(0))
                if observed != {expected_answer}:
                    errors.append(
                        f"{question_id}: reference solver mismatch; "
                        f"expected {expected_answer}, answer option contains {sorted(observed)}"
                    )
            elif question.get("answer", {}).get("canonical") != expected_answer:
                errors.append(
                    f"{question_id}: reference solver mismatch; expected {expected_answer}, "
                    f"stored {question.get('answer', {}).get('canonical')}"
                )
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            errors.append(f"{question_id}: reference solver failed: {exc}")

    content_i18n = question.get("content_i18n")
    if not isinstance(content_i18n, dict):
        errors.append(f"{question_id}: content_i18n must be an object")
        return errors
    if set(content_i18n) != set(LOCALES):
        errors.append(
            f"{question_id}: content_i18n must contain exactly zh-CN and en-US"
        )

    locale_option_ids: dict[str, list[str]] = {}
    for locale in LOCALES:
        content = content_i18n.get(locale)
        if not isinstance(content, dict):
            errors.append(f"{question_id}: missing locale {locale}")
            continue
        for key in ("prompt", "explanation"):
            if not _nonempty_string(content.get(key)):
                errors.append(f"{question_id}: {locale}.{key} must be non-empty")

        if question_type == "single_choice":
            options = content.get("options")
            if not isinstance(options, list) or len(options) != 4:
                errors.append(f"{question_id}: {locale} choice must have four options")
                continue
            option_ids = [item.get("id") for item in options if isinstance(item, dict)]
            option_texts = [item.get("text") for item in options if isinstance(item, dict)]
            if len(option_ids) != 4 or len(set(option_ids)) != 4:
                errors.append(f"{question_id}: {locale} option ids must be unique")
            if set(option_ids) != {"A", "B", "C", "D"}:
                errors.append(f"{question_id}: {locale} option ids must be A/B/C/D")
            normalized_texts = [
                unicodedata.normalize("NFKC", str(text)).strip().casefold()
                for text in option_texts
            ]
            if len(set(normalized_texts)) != 4:
                errors.append(f"{question_id}: {locale} option texts contain duplicates")
            if not all(_nonempty_string(text) for text in option_texts):
                errors.append(f"{question_id}: {locale} option text must be non-empty")
            locale_option_ids[locale] = option_ids

            answer_id = question.get("answer", {}).get("option_id")
            if answer_id not in option_ids:
                errors.append(f"{question_id}: answer.option_id absent from {locale} options")
            distractors = content.get("distractor_explanations")
            expected_distractors = set(option_ids) - {answer_id}
            if not isinstance(distractors, dict) or set(distractors) != expected_distractors:
                errors.append(
                    f"{question_id}: {locale} distractor explanations must cover every wrong option"
                )
            elif not all(_nonempty_string(text) for text in distractors.values()):
                errors.append(f"{question_id}: {locale} distractor explanation is empty")
        elif question_type == "fill_blank":
            if "options" in content:
                errors.append(f"{question_id}: {locale} fill question must omit options")
            if "distractor_explanations" in content:
                errors.append(
                    f"{question_id}: {locale} fill question must omit distractor explanations"
                )

    if question_type == "single_choice":
        if not isinstance(question.get("answer"), dict) or set(question["answer"]) != {
            "option_id"
        }:
            errors.append(f"{question_id}: choice answer must contain only option_id")
        if any(question.get(field) not in ([], None) for field in ("accepted_answers", "regex_answers", "numeric_answer", "numeric_tolerance")):
            errors.append(f"{question_id}: choice must not define fill grading rules")
        if len(locale_option_ids) == 2 and set(locale_option_ids[LOCALES[0]]) != set(
            locale_option_ids[LOCALES[1]]
        ):
            errors.append(f"{question_id}: locale option ids do not match")
    elif question_type == "fill_blank":
        answer = question.get("answer")
        if not isinstance(answer, dict) or not _nonempty_string(answer.get("canonical")):
            errors.append(f"{question_id}: fill answer.canonical must be non-empty")
        accepted = question.get("accepted_answers")
        numeric_answer = question.get("numeric_answer")
        numeric_tolerance = question.get("numeric_tolerance")
        if not isinstance(accepted, list) or not all(
            _nonempty_string(item) for item in accepted
        ):
            errors.append(f"{question_id}: accepted_answers must be a string array")
        if not accepted and numeric_answer is None:
            errors.append(
                f"{question_id}: accepted_answers cannot be empty without numeric grading"
            )
        if numeric_answer is None:
            if numeric_tolerance is not None:
                errors.append(f"{question_id}: numeric_tolerance requires numeric_answer")
        elif not isinstance(numeric_answer, (int, float)) or isinstance(numeric_answer, bool):
            errors.append(f"{question_id}: numeric_answer must be numeric")
        elif not isinstance(numeric_tolerance, (int, float)) or numeric_tolerance < 0:
            errors.append(f"{question_id}: numeric_tolerance must be non-negative")

        regex_answers = question.get("regex_answers")
        if not isinstance(regex_answers, list):
            errors.append(f"{question_id}: regex_answers must be an array")
        else:
            for pattern in regex_answers:
                if not isinstance(pattern, str) or not pattern.startswith("^") or not pattern.endswith("$"):
                    errors.append(f"{question_id}: regex answer must be anchored")
                    continue
                try:
                    re.compile(pattern)
                except re.error as exc:
                    errors.append(f"{question_id}: regex failed to compile: {exc}")
        if isinstance(accepted, list) and isinstance(answer, dict):
            canonical = answer.get("canonical")
            if canonical not in accepted:
                errors.append(f"{question_id}: canonical answer missing from accepted_answers")

    return errors


def _new_stats() -> dict[str, Any]:
    return {
        "total": 0,
        "domain": Counter(),
        "type": Counter(),
        "difficulty": Counter(),
        "domain_type_difficulty": defaultdict(
            lambda: defaultdict(Counter)
        ),
        "families": Counter(),
        "topics": Counter(),
        "verification_method": Counter(),
    }


def _serializable_stats(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "total": stats["total"],
        "domain": dict(sorted(stats["domain"].items())),
        "type": dict(sorted(stats["type"].items())),
        "difficulty": dict(sorted(stats["difficulty"].items())),
        "domain_type_difficulty": {
            domain: {
                question_type: dict(sorted(counts.items()))
                for question_type, counts in sorted(type_counts.items())
            }
            for domain, type_counts in sorted(
                stats["domain_type_difficulty"].items()
            )
        },
        "family_count": len(stats["families"]),
        "families": dict(sorted(stats["families"].items())),
        "topic_count": len(stats["topics"]),
        "topics": dict(sorted(stats["topics"].items())),
        "verification_method": dict(sorted(stats["verification_method"].items())),
    }


def _quota_errors(stats: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if stats["total"] != EXPECTED_COUNTS["total"]:
        errors.append(
            f"quota: expected 1000 questions, found {stats['total']}"
        )
    for dimension in ("domain", "type", "difficulty"):
        actual = dict(stats[dimension])
        expected = EXPECTED_COUNTS[dimension]
        if actual != expected:
            errors.append(f"quota: {dimension} expected {expected}, found {actual}")
    expected_joint = EXPECTED_COUNTS["domain_type_difficulty"]
    for domain in DOMAINS:
        for question_type in QUESTION_TYPES:
            actual = dict(stats["domain_type_difficulty"][domain][question_type])
            expected = expected_joint[domain][question_type]
            if actual != expected:
                errors.append(
                    "quota: joint "
                    f"{domain}/{question_type} expected {expected}, found {actual}"
                )
    # Every required template must be buildable without relaxing any standard-paper constraint.
    for template, domains in {
        "exam-a-sde": ("sde",),
        "exam-d-mle": ("mle",),
        "exam-g-mixed": ("sde", "mle"),
    }.items():
        for question_type, required_by_difficulty in {
            "single_choice": {"L1": 9, "L2": 15, "L3": 6},
            "fill_blank": {"L1": 3, "L2": 5, "L3": 2},
        }.items():
            for difficulty, required in required_by_difficulty.items():
                available = sum(
                    stats["domain_type_difficulty"][domain][question_type][difficulty]
                    for domain in domains
                )
                if available < required:
                    errors.append(
                        f"inventory: {template} lacks {question_type}/{difficulty}: "
                        f"need {required}, have {available}"
                    )
    return errors


def validate_dataset(
    questions: Iterable[dict[str, Any]], *, enforce_quotas: bool = True
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    stats = _new_stats()
    seen_ids: set[str] = set()
    seen_prompts: dict[str, dict[str, str]] = {locale: {} for locale in LOCALES}
    seen_family_parameters: dict[str, dict[str, str]] = defaultdict(dict)

    for line_number, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            errors.append(f"line {line_number}: schema question must be an object")
            continue
        question_id = question.get("id", f"line-{line_number}")
        errors.extend(validate_question(question))
        if question_id in seen_ids:
            errors.append(f"{question_id}: duplicate id")
        seen_ids.add(question_id)

        family_id = question.get("question_family_id")
        parameters = question.get("parameters")
        if isinstance(family_id, str) and isinstance(parameters, dict):
            parameter_key = json.dumps(
                parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            previous = seen_family_parameters[family_id].get(parameter_key)
            if previous is not None:
                errors.append(
                    f"{question_id}: duplicate family parameters of {previous} in {family_id}"
                )
            else:
                seen_family_parameters[family_id][parameter_key] = question_id

        content_i18n = question.get("content_i18n", {})
        for locale in LOCALES:
            prompt = content_i18n.get(locale, {}).get("prompt")
            if not isinstance(prompt, str):
                continue
            fingerprint = canonical_prompt_fingerprint(prompt)
            previous = seen_prompts[locale].get(fingerprint)
            if previous is not None:
                errors.append(
                    f"{question_id}: exact duplicate {locale} prompt of {previous}"
                )
            else:
                seen_prompts[locale][fingerprint] = question_id

        stats["total"] += 1
        domain = question.get("domain")
        question_type = question.get("type")
        difficulty = question.get("difficulty")
        stats["domain"][domain] += 1
        stats["type"][question_type] += 1
        stats["difficulty"][difficulty] += 1
        stats["domain_type_difficulty"][domain][question_type][difficulty] += 1
        stats["families"][question.get("question_family_id")] += 1
        stats["topics"][f"{domain}/{question.get('topic')}"] += 1
        method = question.get("verification", {}).get("method")
        stats["verification_method"][method] += 1

    if enforce_quotas:
        errors.extend(_quota_errors(stats))
    return errors, _serializable_stats(stats)


def _parse_checksum_file(path: Path) -> tuple[dict[str, str], list[str]]:
    checksums: dict[str, str] = {}
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {}, [f"checksum file unreadable: {exc}"]
    for line_number, line in enumerate(lines, start=1):
        parts = line.split("  ", 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            errors.append(f"checksum line {line_number} malformed")
            continue
        checksums[parts[1]] = parts[0]
    return checksums, errors


def validate_manifest(
    root: Path,
    manifest: dict[str, Any],
    checksum_path: Path,
    *,
    actual_count: int,
) -> list[str]:
    errors: list[str] = []
    if manifest.get("format_version") != 1:
        errors.append("manifest format_version must equal 1")
    for key in ("generator", "generator_version", "seed"):
        if not _nonempty_string(manifest.get(key)):
            errors.append(f"manifest {key} must be a non-empty string")
    if manifest.get("locales") != list(LOCALES):
        errors.append(f"manifest locales must equal {list(LOCALES)}")
    if manifest.get("locale_count") != len(LOCALES):
        errors.append(f"manifest locale_count must equal {len(LOCALES)}")
    if manifest.get("logical_question_count") != actual_count:
        errors.append(
            "manifest count mismatch: "
            f"expected {manifest.get('logical_question_count')}, found {actual_count}"
        )
    family_counts = manifest.get("family_variant_counts")
    family_count = manifest.get("family_count")
    if not isinstance(family_counts, dict):
        errors.append("manifest family_variant_counts must be an object")
    else:
        if family_count != len(family_counts):
            errors.append(
                "manifest family_count mismatch: "
                f"expected {family_count}, found {len(family_counts)}"
            )
        if not all(isinstance(value, int) and value > 0 for value in family_counts.values()):
            errors.append("manifest family_variant_counts values must be positive integers")
        elif sum(family_counts.values()) != actual_count:
            errors.append(
                "manifest family_variant_counts total mismatch: "
                f"expected {actual_count}, found {sum(family_counts.values())}"
            )
    review_status = manifest.get("review_status")
    if not isinstance(review_status, dict):
        errors.append("manifest review_status must be an object")
    else:
        if review_status.get("algorithmically_verified") != actual_count:
            errors.append(
                "manifest algorithmically_verified must equal logical question count"
            )
        human_reviewed = review_status.get("human_reviewed")
        if (
            not isinstance(human_reviewed, int)
            or isinstance(human_reviewed, bool)
            or not 0 <= human_reviewed <= actual_count
        ):
            errors.append(
                "manifest human_reviewed must be an integer between zero and logical question count"
            )
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        return errors + ["manifest files must be a non-empty object"]
    checksums, checksum_errors = _parse_checksum_file(checksum_path)
    errors.extend(checksum_errors)
    for relative_path, metadata in files.items():
        target = root / relative_path
        if not target.is_file():
            errors.append(f"manifest file missing: {relative_path}")
            continue
        actual_hash = sha256_file(target)
        expected_hash = metadata.get("sha256") if isinstance(metadata, dict) else None
        if expected_hash != actual_hash:
            errors.append(
                f"manifest hash mismatch for {relative_path}: "
                f"expected {expected_hash}, found {actual_hash}"
            )
        expected_bytes = metadata.get("bytes") if isinstance(metadata, dict) else None
        actual_bytes = target.stat().st_size
        if expected_bytes != actual_bytes:
            errors.append(
                f"manifest byte-size mismatch for {relative_path}: "
                f"expected {expected_bytes}, found {actual_bytes}"
            )
        if checksums.get(relative_path) != actual_hash:
            errors.append(
                f"checksum hash mismatch for {relative_path}: "
                f"expected {checksums.get(relative_path)}, found {actual_hash}"
            )
    extra_checksums = sorted(set(checksums) - set(files))
    if extra_checksums:
        errors.append(f"checksum file contains untracked files: {extra_checksums}")
    return errors


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    questions: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"questions file unreadable: {exc}"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            errors.append(f"line {line_number}: blank JSONL line")
            continue
        try:
            questions.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc}")
    return questions, errors


def run_validation(root: Path) -> dict[str, Any]:
    questions_path = root / "questions.jsonl"
    manifest_path = root / "seed_manifest.json"
    checksum_path = root / "seed_checksums.sha256"
    schema_path = root / "schema.json"

    questions, errors = load_jsonl(questions_path)
    dataset_errors, stats = validate_dataset(questions, enforce_quotas=True)
    errors.extend(dataset_errors)
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append("schema.json must declare JSON Schema draft 2020-12")
        schema_required = set(schema.get("required", []))
        if schema_required != REQUIRED_FIELDS:
            errors.append("schema.json required fields disagree with validator contract")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"schema.json unreadable: {exc}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        errors.extend(
            validate_manifest(
                root, manifest, checksum_path, actual_count=len(questions)
            )
        )
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"seed_manifest.json unreadable: {exc}")

    return {
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "errors": errors,
        "statistics": stats,
        "checks": {
            "schema_and_required_fields": "pass" if not any("schema" in e for e in errors) else "fail",
            "unique_ids": "pass" if not any("duplicate id" in e for e in errors) else "fail",
            "bilingual_content": "pass" if not any("locale" in e or "i18n" in e for e in errors) else "fail",
            "choice_answers_and_distractors": "pass" if not any("option" in e or "distractor" in e for e in errors) else "fail",
            "fill_answers_and_regex": "pass" if not any("accepted" in e or "regex" in e or "numeric" in e for e in errors) else "fail",
            "quota_and_inventory": "pass" if not any("quota" in e or "inventory" in e for e in errors) else "fail",
            "exact_duplicates": "pass" if not any("exact duplicate" in e for e in errors) else "fail",
            "manifest_and_checksums": "pass" if not any("manifest" in e or "checksum" in e or "hash mismatch" in e for e in errors) else "fail",
        },
        "review_status": {
            "algorithmically_verified": len(questions) if not errors else 0,
            "human_reviewed": 0,
            "note": "No claim of subject-matter-expert human review is made.",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "question_bank",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report = run_validation(args.root)
    report_path = args.report or args.root / "validation_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if report["status"] == "pass":
        print(
            "PASS: "
            f"{report['statistics']['total']} questions; "
            f"{report['statistics']['family_count']} families; zero errors"
        )
        return 0
    print(f"FAIL: {report['error_count']} validation errors", file=sys.stderr)
    for error in report["errors"][:50]:
        print(f"- {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
