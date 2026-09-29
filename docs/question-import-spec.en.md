# Question Import Specification

Interview Forge accepts UTF-8 JSONL (one question per line) or JSON (one object or an array) through the Question Bank page or the local API:

- `POST /api/questions/import/preview` validates a batch without writing it.
- `POST /api/questions/import` imports the entire validated batch atomically.

The request body is `{ "filename": "my-bank.jsonl", "content": "..." }`. Preview reports `valid_count`, `invalid_count`, `duplicate_count`, and line-level `errors`. Import additionally reports `imported_count` and `skipped_count`. An identical existing ID is skipped; a conflicting ID is rejected and never overwrites an existing question or attempt.

## Required question shape

Use [`question_bank/schema.json`](../question_bank/schema.json) as the source of truth. Each v2 question includes:

- Stable unique `id`, `domain` (`sde` or `mle`), `topic`, `concept`, `question_family_id`, `difficulty` (`L1`/`L2`/`L3`), and `type` (`single_choice` or `fill_blank`).
- Both `content_i18n.zh-CN` and `content_i18n.en-US`; each needs a natural-language `prompt`, `explanation`, `takeaway`, and `knowledge_card`.
- For single choice: exactly four distinct options (`A`–`D`), `answer.option_id`, and a specific `distractor_explanations` entry for each wrong option.
- Answer metadata (`accepted_answers`, `regex_answers`, `numeric_answer`, `numeric_tolerance`, `parameters`), `verified`, `verification`, and `version`.
- Recommended quality metadata: `question_style`, `cognitive_skill`, `knowledge_points`, `tags`, and `source_refs`.

Question styles are `concept`, `scenario`, `code_reasoning`, `debugging`, `system_design`, `tradeoff`, and `calculation`. Use the tags as metadata, not as a substitute for the actual content of the question.

## Content quality

- Write distractors that a prepared candidate might choose for a specific reason. Each should express a distinct misconception or trade-off and have its own explanation.
- Keep all four options at the same decision level and similar in specificity. Do not make the correct answer uniquely long, polished, or causal, and balance answer positions across the import batch.
- Explain why the answer fits this scenario, including relevant assumptions and boundaries. Make the takeaway transferable; avoid generic interview advice or repeated boilerplate.
- Mix concepts, code reading/debugging, realistic incidents, system design, evaluation, and trade-offs. A style label alone does not make a question that kind of question.
- Avoid number-swapped calculation templates. For L3, the candidate should reason across multiple constraints.
- For version-sensitive topics, include primary documentation or paper URLs in `source_refs` and record a `checked_at` date or version.
- Write both locales as complete, natural versions of the same question and explanation—not partial translations.

The preview checks shape, bilingual fields, duplicate options, missing distractor explanations, common boilerplate, and obvious answer-length signals. Passing validation does not establish subject-matter correctness; review the answer and all three distractors before relying on a generated pack.

## Prompt template

> Generate UTF-8 JSONL questions that conform to `question_bank/schema.json` v2 and this guide. Provide natural English and Simplified Chinese versions of every question. Use realistic MLE/SDE interview scenarios, concepts, code reasoning, debugging, system design, evaluation, and trade-offs. Make every distractor plausible to a prepared candidate and explain its specific misconception. Keep options comparable in length and specificity; balance correct-answer positions across A–D. Avoid generic explanations, number-swapped calculations, and claims unsupported by the scenario. Include primary-source references with a check date for version-sensitive topics. Return only valid JSONL and do not reuse question IDs or question families.

After generation, upload the file in the Question Bank page, inspect the preview, and import only after reviewing the questions themselves.
