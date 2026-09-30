#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_port="${BACKEND_PORT:-8000}"
skip_install=false
if [[ "${1:-}" == "--skip-install" ]]; then
  skip_install=true
fi

command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
command -v npm >/dev/null || { echo "Node.js/npm is required." >&2; exit 1; }

if [[ -f "$project_root/backend/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$project_root/backend/.env"
  set +a
fi

if [[ "$skip_install" == false ]]; then
  (cd "$project_root/backend" && uv sync --extra dev)
  (cd "$project_root/frontend" && npm ci)
fi

backend_pid=""
frontend_pid=""
cleanup() {
  [[ -n "$frontend_pid" ]] && kill "$frontend_pid" 2>/dev/null || true
  [[ -n "$backend_pid" ]] && kill "$backend_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd "$project_root/backend" && uv run uvicorn app.main:app --host 127.0.0.1 --port "$backend_port") &
backend_pid=$!
(cd "$project_root/frontend" && VITE_API_URL="http://127.0.0.1:$backend_port" npm run dev -- --host 127.0.0.1 --port 5173) &
frontend_pid=$!

echo "Interview Forge: http://127.0.0.1:5173 (API: http://127.0.0.1:$backend_port)"
wait "$backend_pid" "$frontend_pid"
