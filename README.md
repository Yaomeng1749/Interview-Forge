# Interview Forge

![Interview Forge — adaptive interview practice](docs/assets/interview-forge-hero.png)

**A bilingual, local interview practice app for software engineering, machine learning engineering, and modern AI systems.**

[简体中文](README.zh-CN.md) · [Question format](docs/question-import-spec.en.md) · [JSON Schema](question_bank/schema.json)

Interview Forge combines timed exams, short practice sessions, explanations, and a review queue. It runs on your computer; attempts and progress live in a local SQLite database. The goal is to learn how to choose an approach under realistic constraints, not just recall a term or multiply numbers.

## Demo

[![Watch the Interview Forge demo: exams, rapid practice, review, and settings](docs/assets/interview-forge-demo-preview.gif)](docs/assets/interview-forge-demo.mp4)

[Watch the full 45-second walkthrough (MP4)](docs/assets/interview-forge-demo.mp4). Recorded from the real app with a fresh local demo database; the optional Jev provider is not configured in this recording.

## What is in the app

| Practice mode | What happens |
| --- | --- |
| Generated A / D / G exams | Build a 40-question SDE, MLE, or mixed paper. A standard paper has 30 single-choice and 10 fill-in questions. Choose a difficulty preset, timer, and question/option shuffling. |
| Four curated papers | A1 (SDE), D1 (MLE), G1 (mixed), and G2 (mixed with more scenarios and trade-offs) are fixed 40-question packs. Their membership stays fixed even when adaptive practice is enabled. |
| Rapid Drill | Practice 20, 40, 80, 160, or an open-ended run. Questions are shuffled from eligible, unseen questions; each answer gets immediate feedback and an explanation. |
| Review and progress | Revisit wrong, due, or bookmarked questions. The dashboard and learning map summarize accuracy and topic mastery. |
| Your own question bank | Preview and import bilingual JSON or JSONL in the Question Bank page. A failed batch is not partially imported, and an existing question ID is not overwritten. |

Questions can test concepts, code reasoning, debugging, system design, evaluation, and trade-offs. The bundled curated sources include SDE fundamentals and MLE/AI topics such as RAG, agents, LLM inference, and model evaluation. These files are maintained manually; the app does not automatically fetch new research or verify every answer with an expert.

## Adaptive practice and Jev

The decision router uses recent answer accuracy, weak topics, concept mastery, and available question counts to plan the next practice segment. **TypeSafe Jev is optional:** when configured and reachable, it chooses one of four difficulty mixes (foundation, standard, intensive, or hard). Local rules calculate topic priorities. If Jev is unavailable, the router falls back to local decision logic.

| Decision point | Effect |
| --- | --- |
| Before a generated A / D / G exam | Select a difficulty mix and topic priorities before the 40 questions are frozen. Your chosen SDE/MLE/mixed track remains in place. |
| After an exam in a multi-paper run | Record a new decision so the next queued paper can reflect the latest results. The paper you just completed does not change. |
| Every 10 Rapid Drill answers | Re-select the *next* block from eligible unseen questions using the new difficulty mix and topic priorities. The current and already answered questions stay put. |
| Fixed curated paper | Keep its 40 question IDs unchanged. Jev does not generate, translate, grade, or rewrite questions. |

Jev receives summary statistics and question-inventory counts for these decisions, not question text or individual answer records. The API key stays in the backend environment; it is not sent to the browser or stored in SQLite. The Settings page shows the most recently used decision provider.

## Run on your computer

### Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 20.19+ (or 22.12+) and npm
- Bash (macOS/Linux; on Windows, use WSL2)

Clone the repository and start both services:

```bash
git clone https://github.com/Yaomeng1749/Interview-Forge.git
cd Interview-Forge
./scripts/start_local.sh
```

The first run installs locked backend and frontend dependencies. To skip installation on later runs when dependencies have not changed:

```bash
./scripts/start_local.sh --skip-install
```

Open the app at <http://127.0.0.1:5173>; interactive API docs are at <http://127.0.0.1:8000/docs>. Press `Ctrl+C` to stop both development servers. If port 8000 is occupied, choose another backend port; the launcher passes it to the frontend automatically:

```bash
BACKEND_PORT=8001 ./scripts/start_local.sh --skip-install
```

### Optional provider configuration

No API key is needed to run the app. To enable Jev, copy the example and set `TYPESAFE_API_KEY` in the local copy. `TYPESAFE_MODEL` defaults to `jev-latest`; change `TYPESAFE_URL` if your account uses another endpoint.

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` locally, then restart the app. The backend reads the key; Git ignores the file. These development servers bind to localhost and are intended for personal use, not multi-user hosting.

## Your data

- Learning history is stored in `backend/data/trainer.db` and is ignored by Git.
- The question bank is stored as JSONL files under `question_bank/`; startup loads the seed bank, curated sources, and fixed exam packs. New rapid sessions draw from eligible active questions rather than the old calculation-only inventory.
- Existing exams keep a snapshot of their questions, so later question-bank changes do not rewrite completed or active exams.
- Back up `backend/data/trainer.db` if you want to preserve your progress when moving computers.

## Bring your own questions

Use the [English import guide](docs/question-import-spec.en.md), [中文导入说明](docs/question-import-spec.md), and [schema](question_bank/schema.json). Each question needs complete English and Simplified Chinese content, an answer, explanations, and verification fields. The in-app preview checks structure and some obvious quality problems before import; it cannot prove that an answer or distractor is technically correct.

## Development checks and current limits

```bash
# Backend
cd backend
uv sync --extra dev
uv run pytest
# Frontend
cd ../frontend
npm ci
npm run test
npm run build
```

Run `python3 scripts/validate_question_bank.py --root question_bank` from the repository root to check the bundled bank. The broader `./scripts/verify_all.sh` also runs lint, coverage, an API smoke test, and browser tests. Backend lint still has legacy findings, so that script is not yet a clean release gate. The app is single-user, has no authentication or cloud sync, and the curated question content still benefits from human review.

## Project map

| Path | Purpose |
| --- | --- |
| `frontend/` | React + TypeScript web application |
| `backend/` | FastAPI API, decision router, grading, and SQLite persistence |
| `question_bank/` | Versioned schema, source questions, and four fixed papers |
| `docs/` | Exam blueprints, API contracts, and import guidance |
| `scripts/` | Local startup and verification helpers |

## License

No license has been added yet. Ask the repository owner before redistributing or reusing this project.
