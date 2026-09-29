# Database migrations

The backend uses an auditable, append-only migration registry. `app.database.run_migrations`
creates SQLAlchemy's declared schema and records `001_initial` in `schema_migrations` in the
same startup operation. Future schema changes must add a new numbered migration and never edit
an already released version.
