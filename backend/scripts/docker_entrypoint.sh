#!/usr/bin/env sh
set -eu

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
UPLOAD_ROOT="${UPLOAD_ROOT:-/app/uploads}"
SKIP_MIGRATIONS="${SKIP_MIGRATIONS:-0}"

ensure_upload_dir() {
  mkdir -p "$UPLOAD_ROOT" 2>/dev/null || true
  if command -v gosu >/dev/null 2>&1; then
    if [ "$(id -u)" = "0" ]; then
      chown -R appuser:appuser "$UPLOAD_ROOT" 2>/dev/null || true
    fi
  fi
}

run_migrations() {
  if [ "$SKIP_MIGRATIONS" = "1" ] || [ "$SKIP_MIGRATIONS" = "true" ]; then
    return 0
  fi

  alembic upgrade head
}

start_app() {
  exec uvicorn app.main:app --host "$HOST" --port "$PORT"
}

ensure_upload_dir

if [ "$(id -u)" = "0" ] && command -v gosu >/dev/null 2>&1; then
  run_migrations
  exec gosu appuser:appuser sh -c "HOST='$HOST' PORT='$PORT' UPLOAD_ROOT='$UPLOAD_ROOT' SKIP_MIGRATIONS='$SKIP_MIGRATIONS' uvicorn app.main:app --host '$HOST' --port '$PORT'"
else
  run_migrations
  start_app
fi
