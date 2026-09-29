# Shared implementation contract

This file is the integration boundary for the bilingual local-first MVP.

## Locale and identifiers

- Supported locales are `zh-CN` and `en-US`.
- Stable identifiers (`domain`, `topic`, `concept`, option IDs, template IDs) are locale-neutral.
- A built exam freezes its locale and complete question/answer snapshots.
- Public in-progress exam responses must omit answers, explanations, grading rules, and correctness.

## Question source format

Question-bank source files are JSONL. Each logical question has one ID and both locales:

```json
{
  "id": "sde-complexity-0001",
  "domain": "sde",
  "topic": "data_structures_algorithms",
  "concept": "complexity",
  "question_family_id": "complexity_lookup",
  "difficulty": "L1",
  "type": "single_choice",
  "content_i18n": {
    "zh-CN": {
      "prompt": "...",
      "options": [{"id": "A", "text": "..."}],
      "explanation": "...",
      "distractor_explanations": {"B": "..."}
    },
    "en-US": {
      "prompt": "...",
      "options": [{"id": "A", "text": "..."}],
      "explanation": "...",
      "distractor_explanations": {"B": "..."}
    }
  },
  "answer": {"option_id": "A"},
  "accepted_answers": [],
  "regex_answers": [],
  "numeric_answer": null,
  "numeric_tolerance": null,
  "verified": true,
  "verification": {"method": "deterministic_template", "evidence": "..."},
  "version": 1
}
```

Fill-in questions omit `options` and use one or more accepted answers, optional anchored regexes, or a numeric answer and tolerance.

## Required exam invariants

- Standard paper: 40 questions, 60 minutes, 30 single-choice + 10 fill-in.
- Standard difficulty: exactly L1/L2/L3 = 12/20/8.
- Scores: choice 2 points, fill-in 4 points, total 100.
- Required templates: `exam-a-sde`, `exam-d-mle`, and `exam-g-mixed`.
- Inventory shortages fail closed with HTTP 409; constraints are never silently relaxed.
- Answer autosaves use monotonically increasing client revisions.
- Submission is idempotent and atomically updates attempts, mastery, and review queue.

## HTTP boundary

Backend base URL is `http://127.0.0.1:8000`; frontend reads `VITE_API_URL` and defaults to that URL.

Core routes:

- `GET /api/health`
- `GET /api/exam-templates`
- `POST /api/exams/build`
- `GET /api/exams/active`
- `GET /api/exams/{id}`
- `PUT /api/exams/{id}/answers/{position}`
- `PUT /api/exams/{id}/flags/{position}`
- `POST /api/exams/{id}/submit`
- `GET /api/exams/{id}/result`
- `GET /api/exams/history`
- `POST /api/drill/session`
- `GET /api/drill/{id}/next`
- `POST /api/drill/{id}/answer`
- `POST /api/drill/{id}/finish`
- `GET /api/questions`
- `GET /api/questions/{id}`
- `GET /api/review/wrong`
- `GET /api/review/due`
- `GET /api/review/bookmarked`
- `POST /api/review/build-exam`
- `GET /api/stats/dashboard`
- `GET /api/stats/topics`
- `GET /api/stats/daily`
- `GET /api/stats/exams`
- `GET /api/settings/provider/status`
- `POST /api/settings/provider/test`
- `GET /api/settings`
- `PUT /api/settings`

## Secret boundary

Provider keys are read only from environment variables. They must not be persisted, logged, serialized into HTTP responses, or embedded in the frontend.
