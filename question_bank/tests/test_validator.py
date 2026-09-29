from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validate_question_bank import (  # noqa: E402
    EXPECTED_COUNTS,
    canonical_prompt_fingerprint,
    sha256_file,
    validate_dataset,
    validate_manifest,
    validate_question,
)
from scripts.generate_question_bank import generate_questions  # noqa: E402


def valid_choice(question_id: str = "sde-algorithms-0001") -> dict:
    return {
        "id": question_id,
        "domain": "sde",
        "topic": "data_structures_algorithms",
        "concept": "binary_search",
        "question_family_id": "binary_search_comparisons",
        "difficulty": "L1",
        "type": "single_choice",
        "content_i18n": {
            "zh-CN": {
                "prompt": "在 64 个已排序且互异的元素中，二分查找最多需要多少次比较？",
                "options": [
                    {"id": "A", "text": "5"},
                    {"id": "B", "text": "6"},
                    {"id": "C", "text": "7"},
                    {"id": "D", "text": "64"},
                ],
                "explanation": "最坏比较次数为 floor(log2(n)) + 1，因此答案为 7。",
                "distractor_explanations": {
                    "A": "少算了两层。",
                    "B": "log2(n) 是层数边界，比较次数还需加一。",
                    "D": "这是线性查找的上界。",
                },
            },
            "en-US": {
                "prompt": "Among 64 sorted distinct elements, what is the maximum number of comparisons for binary search?",
                "options": [
                    {"id": "A", "text": "5"},
                    {"id": "B", "text": "6"},
                    {"id": "C", "text": "7"},
                    {"id": "D", "text": "64"},
                ],
                "explanation": "The worst case is floor(log2(n)) + 1, so the answer is 7.",
                "distractor_explanations": {
                    "A": "This undercounts by two levels.",
                    "B": "log2(n) bounds the levels; one more comparison is required.",
                    "D": "This is the linear-search bound.",
                },
            },
        },
        "answer": {"option_id": "C"},
        "accepted_answers": [],
        "regex_answers": [],
        "numeric_answer": None,
        "numeric_tolerance": None,
        "parameters": {"n": 64},
        "verified": True,
        "verification": {
            "method": "reference_solver",
            "solver": "binary_comparisons",
            "solver_version": "1",
            "evidence": "floor(log2(64)) + 1 = 7",
        },
        "version": 1,
    }


def valid_fill(question_id: str = "mle-metrics-0001") -> dict:
    question = valid_choice(question_id)
    question.update(
        {
            "domain": "mle",
            "topic": "classical_ml",
            "concept": "precision",
            "question_family_id": "precision_from_counts",
            "difficulty": "L2",
            "type": "fill_blank",
            "content_i18n": {
                "zh-CN": {
                    "prompt": "若 TP=36、FP=12，precision 是多少？请填小数。",
                    "explanation": "precision = TP/(TP+FP) = 36/48 = 0.75。",
                },
                "en-US": {
                    "prompt": "If TP=36 and FP=12, what is precision? Enter a decimal.",
                    "explanation": "precision = TP/(TP+FP) = 36/48 = 0.75.",
                },
            },
            "answer": {"canonical": "0.75"},
            "accepted_answers": ["0.75", ".75"],
            "regex_answers": [r"^(?:0?\.75)$"],
            "numeric_answer": 0.75,
            "numeric_tolerance": 0.000001,
            "parameters": {"tp": 36, "fp": 12},
            "verification": {
                "method": "reference_solver",
                "solver": "precision",
                "solver_version": "1",
                "evidence": "36 / (36 + 12) = 0.75",
            },
        }
    )
    return question


class QuestionValidationTests(unittest.TestCase):
    def test_valid_choice_passes(self) -> None:
        self.assertEqual(validate_question(valid_choice()), [])

    def test_valid_fill_passes(self) -> None:
        self.assertEqual(validate_question(valid_fill()), [])

    def test_requires_both_locales(self) -> None:
        question = valid_choice()
        del question["content_i18n"]["en-US"]
        errors = validate_question(question)
        self.assertTrue(any("en-US" in error for error in errors), errors)

    def test_executes_schema_additional_properties_and_unique_items(self) -> None:
        question = valid_fill()
        question["unexpected"] = True
        question["accepted_answers"] = ["0.75", "0.75"]
        del question["verification"]["solver_version"]
        errors = validate_question(question)
        self.assertTrue(any("unexpected" in error for error in errors), errors)
        self.assertTrue(any("uniqueItems" in error for error in errors), errors)
        self.assertTrue(any("solver_version" in error for error in errors), errors)

    def test_choice_answer_must_exist_and_distractors_cover_wrong_options(self) -> None:
        question = valid_choice()
        question["answer"]["option_id"] = "Z"
        del question["content_i18n"]["zh-CN"]["distractor_explanations"]["A"]
        errors = validate_question(question)
        self.assertTrue(any("option_id" in error for error in errors), errors)
        self.assertTrue(any("distractor" in error for error in errors), errors)

    def test_fill_requires_answers_and_compilable_anchored_regex(self) -> None:
        question = valid_fill()
        question["accepted_answers"] = []
        question["numeric_answer"] = None
        question["numeric_tolerance"] = None
        question["regex_answers"] = ["([unterminated"]
        errors = validate_question(question)
        self.assertTrue(any("accepted" in error for error in errors), errors)
        self.assertTrue(any("regex" in error for error in errors), errors)

    def test_dataset_rejects_duplicate_ids_and_exact_prompts(self) -> None:
        first = valid_choice()
        duplicate = copy.deepcopy(first)
        errors, _ = validate_dataset([first, duplicate], enforce_quotas=False)
        self.assertTrue(any("duplicate id" in error for error in errors), errors)
        self.assertTrue(any("exact duplicate" in error for error in errors), errors)

    def test_prompt_fingerprint_normalizes_case_and_whitespace(self) -> None:
        first = "  Binary   Search\nneeds 7 comparisons. "
        second = "binary search needs 7 comparisons."
        self.assertEqual(
            canonical_prompt_fingerprint(first), canonical_prompt_fingerprint(second)
        )

    def test_quota_gate_rejects_small_dataset(self) -> None:
        errors, stats = validate_dataset(
            [valid_choice(), valid_fill()], enforce_quotas=True
        )
        self.assertEqual(stats["total"], 2)
        self.assertTrue(any("expected 1000" in error for error in errors), errors)
        self.assertEqual(EXPECTED_COUNTS["difficulty"], {"L1": 300, "L2": 500, "L3": 200})

    def test_reference_solver_is_recomputed(self) -> None:
        question = valid_choice()
        question["verification"].update(
            {"solver": "binary_comparisons", "solver_version": "1"}
        )
        question["parameters"] = {"n": 8}
        errors = validate_question(question)
        self.assertTrue(any("reference solver mismatch" in error for error in errors), errors)

    def test_family_parameters_must_be_unique(self) -> None:
        first = valid_choice()
        second = copy.deepcopy(first)
        second["id"] = "sde-algorithms-0002"
        second["content_i18n"]["zh-CN"]["prompt"] += "（变式二）"
        second["content_i18n"]["en-US"]["prompt"] += " (variant two)"
        errors, _ = validate_dataset([first, second], enforce_quotas=False)
        self.assertTrue(any("duplicate family parameters" in error for error in errors), errors)

    def test_generated_distractor_explanations_are_value_specific(self) -> None:
        choice = next(
            question
            for question in generate_questions()
            if question["type"] == "single_choice"
        )
        answer_id = choice["answer"]["option_id"]
        for locale in ("zh-CN", "en-US"):
            content = choice["content_i18n"][locale]
            explanations = content["distractor_explanations"]
            self.assertEqual(len(set(explanations.values())), 3)
            for option in content["options"]:
                if option["id"] != answer_id:
                    self.assertIn(option["text"], explanations[option["id"]])


class ManifestValidationTests(unittest.TestCase):
    def test_manifest_and_checksum_match_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            questions_path = root / "questions.jsonl"
            questions_path.write_text(
                json.dumps(valid_choice(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            digest = sha256_file(questions_path)
            manifest = {
                "format_version": 1,
                "generator": "scripts/generate_question_bank.py",
                "generator_version": "bank-v1.0.0",
                "seed": "test-seed",
                "logical_question_count": 1,
                "locale_count": 2,
                "locales": ["zh-CN", "en-US"],
                "family_count": 1,
                "family_variant_counts": {"binary_search_comparisons": 1},
                "quota": {},
                "review_status": {"algorithmically_verified": 1, "human_reviewed": 0},
                "files": {"questions.jsonl": {"sha256": digest, "bytes": questions_path.stat().st_size}},
            }
            checksum_path = root / "seed_checksums.sha256"
            checksum_path.write_text(f"{digest}  questions.jsonl\n", encoding="utf-8")
            self.assertEqual(
                validate_manifest(root, manifest, checksum_path, actual_count=1), []
            )

    def test_manifest_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            questions_path = root / "questions.jsonl"
            questions_path.write_text("before\n", encoding="utf-8")
            digest = hashlib.sha256(b"before\n").hexdigest()
            manifest = {
                "format_version": 1,
                "generator": "scripts/generate_question_bank.py",
                "generator_version": "bank-v1.0.0",
                "seed": "test-seed",
                "logical_question_count": 1,
                "locale_count": 2,
                "locales": ["zh-CN", "en-US"],
                "family_count": 1,
                "family_variant_counts": {"binary_search_comparisons": 1},
                "quota": {},
                "review_status": {"algorithmically_verified": 1, "human_reviewed": 0},
                "files": {"questions.jsonl": {"sha256": digest, "bytes": len(b"before\n")}},
            }
            checksum_path = root / "seed_checksums.sha256"
            checksum_path.write_text(f"{digest}  questions.jsonl\n", encoding="utf-8")
            questions_path.write_text("after\n", encoding="utf-8")
            errors = validate_manifest(root, manifest, checksum_path, actual_count=1)
            self.assertTrue(any("hash mismatch" in error for error in errors), errors)

    def test_manifest_detects_audit_metadata_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            questions_path = root / "questions.jsonl"
            questions_path.write_text("{}\n", encoding="utf-8")
            digest = sha256_file(questions_path)
            checksum_path = root / "seed_checksums.sha256"
            checksum_path.write_text(f"{digest}  questions.jsonl\n", encoding="utf-8")
            manifest = {
                "format_version": 1,
                "generator": "scripts/generate_question_bank.py",
                "generator_version": "bank-v1.0.0",
                "seed": "test-seed",
                "logical_question_count": 1,
                "locale_count": 999,
                "locales": ["zh-CN", "en-US"],
                "family_count": 999,
                "family_variant_counts": {},
                "quota": {},
                "review_status": {"algorithmically_verified": 1, "human_reviewed": 1000},
                "files": {"questions.jsonl": {"sha256": digest, "bytes": 1}},
            }
            errors = validate_manifest(root, manifest, checksum_path, actual_count=1)
            self.assertTrue(any("locale_count" in error for error in errors), errors)
            self.assertTrue(any("family_count" in error for error in errors), errors)
            self.assertTrue(any("human_reviewed" in error for error in errors), errors)
            self.assertTrue(any("byte-size" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
