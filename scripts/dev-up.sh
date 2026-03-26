#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/.run"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_PORT="${BACKEND_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"

mkdir -p "$LOG_DIR"

wait_for_http() {
  local url="$1"
  local name="$2"
  local attempts="${3:-20}"

  for _ in $(seq 1 "$attempts"); do
    if curl --noproxy '*' -fsS "$url" >/dev/null 2>&1; then
      echo "[dev-up] $name is ready at $url"
      return 0
    fi
    sleep 1
  done

  echo "[dev-up] $name failed to become ready: $url" >&2
  return 1
}

if [ ! -d "$BACKEND_DIR/.venv" ]; then
  echo "[dev-up] Creating backend virtualenv with uv..."
  uv venv "$BACKEND_DIR/.venv"
fi

echo "[dev-up] Installing backend dependencies..."
(cd "$BACKEND_DIR" && uv sync --all-groups)

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "[dev-up] Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
fi

if [ -f "$LOG_DIR/backend.pid" ] && kill -0 "$(cat "$LOG_DIR/backend.pid")" 2>/dev/null; then
  echo "[dev-up] Backend already running on PID $(cat "$LOG_DIR/backend.pid")"
else
  echo "[dev-up] Starting FastAPI on $BACKEND_PORT..."
  nohup bash -lc "
    cd "$BACKEND_DIR"
    exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT
  " >"$LOG_DIR/backend.log" 2>&1 &
  echo $! >"$LOG_DIR/backend.pid"
fi

if [ -f "$LOG_DIR/worker.pid" ] && kill -0 "$(cat "$LOG_DIR/worker.pid")" 2>/dev/null; then
  echo "[dev-up] Worker already running on PID $(cat "$LOG_DIR/worker.pid")"
else
  echo "[dev-up] Starting worker..."
  nohup bash -lc "
    cd "$BACKEND_DIR"
    exec .venv/bin/python -m app.worker
  " >"$LOG_DIR/worker.log" 2>&1 &
  echo $! >"$LOG_DIR/worker.pid"
fi

if [ -f "$LOG_DIR/frontend.pid" ] && kill -0 "$(cat "$LOG_DIR/frontend.pid")" 2>/dev/null; then
  echo "[dev-up] Frontend already running on PID $(cat "$LOG_DIR/frontend.pid")"
else
  echo "[dev-up] Starting Vite on $FRONTEND_PORT..."
  nohup bash -lc "
    cd "$FRONTEND_DIR"
    export VITE_API_BASE_URL=http://127.0.0.1:$BACKEND_PORT
    exec npm run dev -- --host 127.0.0.1 --port $FRONTEND_PORT
  " >"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$LOG_DIR/frontend.pid"
fi

echo "[dev-up] Services starting..."
echo "  backend log : $LOG_DIR/backend.log"
echo "  worker log  : $LOG_DIR/worker.log"
echo "  frontend log: $LOG_DIR/frontend.log"
echo "  app url     : http://127.0.0.1:$FRONTEND_PORT"

wait_for_http "http://127.0.0.1:$BACKEND_PORT/health" "backend"
wait_for_http "http://127.0.0.1:$FRONTEND_PORT" "frontend"
