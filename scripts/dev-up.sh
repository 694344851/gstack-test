#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/.run"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
ENV_FILE="${ENV_FILE:-$ROOT/.env.local}"
BACKEND_PORT="${BACKEND_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"
BACKEND_BIN="$BACKEND_DIR/.venv/bin/python"
FRONTEND_BIN="$FRONTEND_DIR/node_modules/.bin/vite"
BACKEND_PATTERN="$BACKEND_BIN -m uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT"
WORKER_PATTERN="$BACKEND_BIN -m app.worker"
FRONTEND_PATTERN="$FRONTEND_BIN --host 127.0.0.1 --port $FRONTEND_PORT"

mkdir -p "$LOG_DIR"

if [ -f "$ENV_FILE" ]; then
  echo "[dev-up] Loading env from $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

port_pids() {
  local port="$1"
  ss -ltnp 2>/dev/null | awk -v port=":$port" '$4 ~ port"$" { print $NF }' | rg -o 'pid=[0-9]+' | cut -d= -f2 | sort -u || true
}

command_pids() {
  local pattern="$1"
  pgrep -f -- "$pattern" | sort -u || true
}

graceful_kill() {
  local pid="$1"

  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi

  kill "$pid" 2>/dev/null || true

  for _ in $(seq 1 20); do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.2
  done

  kill -9 "$pid" 2>/dev/null || true
}

ensure_port_free() {
  local port="$1"
  local label="$2"
  local pids
  pids="$(port_pids "$port")"

  if [ -z "$pids" ]; then
    return 0
  fi

  echo "[dev-up] $label port $port is busy; reclaiming stale listener(s): $pids"
  for pid in $pids; do
    graceful_kill "$pid"
  done

  sleep 1

  if [ -n "$(port_pids "$port")" ]; then
    echo "[dev-up] Failed to free $label port $port" >&2
    return 1
  fi
}

ensure_command_free() {
  local pattern="$1"
  local label="$2"
  local pids
  pids="$(command_pids "$pattern")"

  if [ -z "$pids" ]; then
    return 0
  fi

  echo "[dev-up] Found stale $label process(es): $pids"
  for pid in $pids; do
    graceful_kill "$pid"
  done

  sleep 1

  if [ -n "$(command_pids "$pattern")" ]; then
    echo "[dev-up] Failed to reclaim stale $label process(es)" >&2
    return 1
  fi
}

wait_for_pid_file() {
  local pid_file="$1"
  local label="$2"

  for _ in $(seq 1 20); do
    if [ -s "$pid_file" ]; then
      return 0
    fi
    sleep 0.2
  done

  echo "[dev-up] $label did not create pid file: $pid_file" >&2
  return 1
}

ensure_pid_running() {
  local pid="$1"
  local label="$2"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "[dev-up] $label failed to stay running (PID $pid)" >&2
    return 1
  fi
}

start_detached() {
  local label="$1"
  local workdir="$2"
  local logfile="$3"
  local pid_file="$4"
  shift 4

  rm -f "$pid_file"
  : >"$logfile"

  setsid -f bash -lc '
    cd "$1"
    echo $$ > "$2"
    shift 2
    exec "$@"
  ' bash "$workdir" "$pid_file" "$@" </dev/null >>"$logfile" 2>&1

  wait_for_pid_file "$pid_file" "$label"
  ensure_pid_running "$(cat "$pid_file")" "$label"
}

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

ensure_port_free "$BACKEND_PORT" "backend"
ensure_port_free "$FRONTEND_PORT" "frontend"
ensure_command_free "$WORKER_PATTERN" "worker"
ensure_command_free "$BACKEND_PATTERN" "backend"
ensure_command_free "$FRONTEND_PATTERN" "frontend"

if [ -f "$LOG_DIR/backend.pid" ] && kill -0 "$(cat "$LOG_DIR/backend.pid")" 2>/dev/null; then
  echo "[dev-up] Backend already running on PID $(cat "$LOG_DIR/backend.pid")"
else
  echo "[dev-up] Starting FastAPI on $BACKEND_PORT..."
  start_detached \
    "backend" \
    "$BACKEND_DIR" \
    "$LOG_DIR/backend.log" \
    "$LOG_DIR/backend.pid" \
    "$BACKEND_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
fi

if [ -f "$LOG_DIR/worker.pid" ] && kill -0 "$(cat "$LOG_DIR/worker.pid")" 2>/dev/null; then
  echo "[dev-up] Worker already running on PID $(cat "$LOG_DIR/worker.pid")"
else
  echo "[dev-up] Starting worker..."
  start_detached \
    "worker" \
    "$BACKEND_DIR" \
    "$LOG_DIR/worker.log" \
    "$LOG_DIR/worker.pid" \
    "$BACKEND_BIN" -m app.worker
fi

if [ -f "$LOG_DIR/frontend.pid" ] && kill -0 "$(cat "$LOG_DIR/frontend.pid")" 2>/dev/null; then
  echo "[dev-up] Frontend already running on PID $(cat "$LOG_DIR/frontend.pid")"
else
  echo "[dev-up] Starting Vite on $FRONTEND_PORT..."
  start_detached \
    "frontend" \
    "$FRONTEND_DIR" \
    "$LOG_DIR/frontend.log" \
    "$LOG_DIR/frontend.pid" \
    env "VITE_API_BASE_URL=http://127.0.0.1:$BACKEND_PORT" \
    "$FRONTEND_BIN" --host 127.0.0.1 --port "$FRONTEND_PORT"
fi

echo "[dev-up] Services starting..."
echo "  backend log : $LOG_DIR/backend.log"
echo "  worker log  : $LOG_DIR/worker.log"
echo "  frontend log: $LOG_DIR/frontend.log"
echo "  app url     : http://127.0.0.1:$FRONTEND_PORT"

wait_for_http "http://127.0.0.1:$BACKEND_PORT/health" "backend"
wait_for_http "http://127.0.0.1:$FRONTEND_PORT" "frontend"
