# 001_initial

Creates: `questions`, `exam_sessions`, `attempts`, `concept_mastery`, `review_queue`,
`drill_sessions`, `settings`, `decision_logs`, and `schema_migrations`.

The executable declaration is `app/models.py`; the idempotent runner and version receipt are in
`app/database.py`. The migration is applied automatically during FastAPI lifespan startup.
