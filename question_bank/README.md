# Bilingual MLE/SDE question bank

`questions.jsonl` contains the original **1,000 legacy generated questions**. Each JSONL record has one
locale-neutral ID and complete `zh-CN` plus `en-US` content. The bank is split
50/50 between SDE and MLE, contains 740 single-choice and 260 fill-in questions,
and has the exact L1/L2/L3 distribution 300/500/200.

## Reproduce and validate

From the repository root:

```bash
python3 scripts/generate_question_bank.py --output question_bank
python3 scripts/validate_question_bank.py --root question_bank
python3 -m unittest discover -s question_bank/tests -v
```

Generation does not use wall-clock time, Python `hash()`, an LLM, or global
random state. Parameters are derived from SHA-256 of the generator seed,
family ID, variant index, and parameter name. Every stored answer is produced
by a pure reference solver. `seed_manifest.json` records the generator version,
family inventory, quota, and protected file hashes; `seed_checksums.sha256`
duplicates the protected hashes in standard checksum form.

## Verification boundary

`verified=true` means the record passed deterministic structural checks and its
answer came from the named reference solver. It does **not** mean that 1,000
questions were independently reviewed by a subject-matter expert. The shipped
validation report therefore keeps `algorithmically_verified` and
`human_reviewed` separate; the latter is zero until a real review is recorded.

Choice distractors are numeric alternatives and every wrong option has a
bilingual explanation. Fill-in grading includes a canonical answer, accepted
aliases, an anchored regular expression, and numeric tolerance. Runtime grading
should normalize Unicode, trim whitespace, case-fold aliases, then apply regex
and numeric tolerance. During an in-progress exam, applications must project
away answers, explanations, verification evidence, and grading rules as required
by `docs/contracts.md`.
# Question bank

`questions.jsonl` is the original immutable v1 seed. `curated_sources/*.jsonl` is
the append-only v2 bank used preferentially for new exams and rapid practice. Existing attempts
remain linked to their original question IDs. See `../docs/question-import-spec.md` for the local
JSON/JSONL import contract and `../scripts/cleanup_unattempted_legacy_questions.py` for the
explicit, gated cleanup of unused v1 rows.
