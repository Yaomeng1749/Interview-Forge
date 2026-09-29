#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$project_root/.aris/runtime"
runtime_dir="$(mktemp -d "$project_root/.aris/runtime/verify.XXXXXX")"
backend_pid=""
cleanup() {
  [[ -n "$backend_pid" ]] && kill "$backend_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

python3 "$project_root/scripts/validate_question_bank.py" --root "$project_root/question_bank"

(cd "$project_root/backend" && uv sync --extra dev)
(cd "$project_root/backend" && uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80)
(cd "$project_root/backend" && uv run ruff check .)

(cd "$project_root/frontend" && npm ci)
(cd "$project_root/frontend" && npm run lint)
(cd "$project_root/frontend" && npm run test:coverage)
(cd "$project_root/frontend" && npm run build)

DATABASE_URL="sqlite:///$runtime_dir/trainer.db" \
QUESTION_BANK_PATH="$project_root/question_bank/questions.jsonl" \
  "$project_root/backend/.venv/bin/uvicorn" app.main:app \
  --app-dir "$project_root/backend" --host 127.0.0.1 --port 8010 \
  >"$runtime_dir/backend.log" 2>&1 &
backend_pid=$!

for _ in {1..50}; do
  if curl --fail --silent http://127.0.0.1:8010/api/health >/dev/null; then
    break
  fi
  sleep 0.1
done
curl --fail --silent http://127.0.0.1:8010/api/health >/dev/null
python3 "$project_root/scripts/smoke_api.py" --base http://127.0.0.1:8010
(cd "$project_root/frontend" && VITE_API_URL=http://127.0.0.1:8010 npm run e2e)

echo "PASS: all deterministic gates and live E2E completed"
