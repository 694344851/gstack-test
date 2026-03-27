#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/.run"
BACKEND_PORT="${BACKEND_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_BIN="$BACKEND_DIR/.venv/bin/python"
FRONTEND_BIN="$FRONTEND_DIR/node_modules/.bin/vite"
BACKEND_PATTERN="$BACKEND_BIN -m uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT"
WORKER_PATTERN="$BACKEND_BIN -m app.worker"
FRONTEND_PATTERN="$FRONTEND_BIN --host 127.0.0.1 --port $FRONTEND_PORT"

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

stop_pid_file() {
  local name="$1"
  local pid_file="$LOG_DIR/$name.pid"
  if [ -f "$pid_file" ]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "[dev-down] Stopping $name (PID $pid)"
      graceful_kill "$pid"
    fi
    rm -f "$pid_file"
  fi
}

stop_port_listener() {
  local port="$1"
  local label="$2"
  local pids
  pids="$(ss -ltnp 2>/dev/null | awk -v port=":$port" '$4 ~ port"$" { print $NF }' | rg -o 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"

  if [ -z "$pids" ]; then
    return 0
  fi

  for pid in $pids; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "[dev-down] Reclaiming $label port $port from PID $pid"
      graceful_kill "$pid"
    fi
  done
}

stop_matching_processes() {
  local pattern="$1"
  local label="$2"
  local pids
  pids="$(pgrep -f -- "$pattern" | sort -u || true)"

  if [ -z "$pids" ]; then
    return 0
  fi

  for pid in $pids; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "[dev-down] Clearing stale $label process PID $pid"
      graceful_kill "$pid"
    fi
  done
}

for name in frontend worker backend; do
  stop_pid_file "$name"
done

# 旧的 dev-up 可能留下了失联进程，单靠 pid 文件不够。
stop_port_listener "$FRONTEND_PORT" "frontend"
stop_port_listener "$BACKEND_PORT" "backend"
stop_matching_processes "$WORKER_PATTERN" "worker"
stop_matching_processes "$BACKEND_PATTERN" "backend"
stop_matching_processes "$FRONTEND_PATTERN" "frontend"

echo "[dev-down] Done."
