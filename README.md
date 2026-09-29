# Interview Forge

![Interview Forge — adaptive interview practice](docs/assets/interview-forge-hero.png)

**A local-first, bilingual interview practice studio for MLE, SDE, and modern AI systems.**

Build adaptive exams, practice in short randomized sessions, review mistakes, and import your own question sets. The app runs on your computer and stores learning history in a local SQLite database.

> English is the primary documentation language. [简体中文说明](README.zh-CN.md)

## What you can do

- Build timed 40-question exams for software engineering, machine learning, or a mixed track.
- Use Rapid Drill for randomized practice; answered questions are kept for review instead of being silently repeated.
- Switch the interface and question explanations between English and Simplified Chinese.
- Review mistakes, bookmarks, topic progress, and per-question explanations.
- Import bilingual JSON/JSONL question banks after a preview and validation pass.
- Optionally connect a decision provider for adaptive difficulty. The app can fall back to its local rule-based provider.

## Run locally

### Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 20.19+ (or 22.12+) and npm
- Bash (macOS/Linux; on Windows, use WSL2)

Clone the repository, enter its directory, then run:

```bash
./scripts/start_local.sh
```

On first run, the script installs the locked backend and frontend dependencies. To skip dependency installation on later runs:

```bash
./scripts/start_local.sh --skip-install
```

Open the app at <http://127.0.0.1:5173>. The API and interactive API docs are at <http://127.0.0.1:8000> and <http://127.0.0.1:8000/docs>. Press `Ctrl+C` in the terminal to stop both services. The development servers bind to localhost; this setup is for personal/local use, not production hosting.

### Optional provider configuration

The app does not require a paid API key. To configure an optional provider, copy the example and edit it locally:

```bash
cp backend/.env.example backend/.env
```

Keep credentials in `backend/.env` or your shell environment—never commit them. When an external decision provider is enabled, the provider receives aggregate learner progress and question-inventory metadata used to choose difficulty/topic weights. Question text and answer history are not sent as part of that decision request. Without a working provider, the app ultimately uses its local rule-based decision logic.

## Your data

- Learning history is stored in `backend/data/trainer.db` and is ignored by Git.
- The question bank is stored as JSONL files under `question_bank/`; the app loads the legacy bank, curated sources, and fixed exam packs on startup.
- Existing exams keep a snapshot of their questions, so later question-bank changes do not rewrite completed or active exams.
- Back up `backend/data/trainer.db` if you want to preserve your progress when moving computers.

## Bring your own questions

Use the [English import guide](docs/question-import-spec.en.md), [中文导入说明](docs/question-import-spec.md), and [schema](question_bank/schema.json). Each question needs English and Simplified Chinese content. The in-app import preview reports invalid records before you confirm an import; invalid batches are not partially written, and conflicting IDs do not overwrite existing questions.

## Development checks

```bash
# Backend
cd backend
uv sync --extra dev
uv run pytest
uv run ruff check .

# Frontend
cd ../frontend
npm ci
npm run test
npm run build
```

For the full local verification workflow, run `./scripts/verify_all.sh` from the repository root. It runs the question-bank validator, backend and frontend checks, an API smoke test, and browser end-to-end tests.

## Project map

| Path | Purpose |
| --- | --- |
| `frontend/` | React + TypeScript web application |
| `backend/` | FastAPI service, SQLite persistence, exam and drill logic |
| `question_bank/` | Versioned question schema, source questions, and curated fixed papers |
| `docs/` | Exam blueprints, API contracts, and import guidance |
| `scripts/` | Local startup and verification helpers |

## License

No license has been added yet. Ask the repository owner before redistributing or reusing this project.
