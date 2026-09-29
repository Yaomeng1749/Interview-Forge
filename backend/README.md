# Adaptive Exam Backend

FastAPI + SQLAlchemy backend for Interview Forge. See the repository [README](../README.md) for local setup and [README.zh-CN.md](../README.zh-CN.md) for the Chinese guide.

## Local development

```bash
uv sync --extra dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

SQLite is created and migrated automatically. The default database is `backend/data/trainer.db`; set `DATABASE_URL` to use a different local database. On startup, the app loads `question_bank/questions.jsonl`, every `question_bank/curated_sources/*.jsonl`, and every `question_bank/curated_packs/*.jsonl`. Setting `QUESTION_BANK_PATH` intentionally overrides this and loads only the specified file.

Optional provider settings are read from environment variables (the root startup script loads `backend/.env`). Keep secrets out of source control. Without an available decision provider, the router falls back to local rule-based decisions.

Validation:

```bash
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
uv run ruff check .
```

Provider keys are read only from environment variables. They are never stored, logged, or
returned from an API.
