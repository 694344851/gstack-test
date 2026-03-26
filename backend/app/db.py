from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DB_ENV = "GSTACK_TEST_DB_PATH"
DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "app.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path() -> Path:
    return Path(os.environ.get(DB_ENV, DEFAULT_DB))


def init_db() -> None:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generation_tasks (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                input_json TEXT NOT NULL,
                stage_artifacts_json TEXT NOT NULL,
                current_result_json TEXT NOT NULL,
                error_json TEXT,
                claimed_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


@contextmanager
def connect() -> sqlite3.Connection:
    init_db()
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_task_row(task: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO generation_tasks (
                id, status, current_stage, input_json, stage_artifacts_json,
                current_result_json, error_json, claimed_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["id"],
                task["status"],
                task["current_stage"],
                json.dumps(task["input"], ensure_ascii=False),
                json.dumps(task["stages"], ensure_ascii=False),
                json.dumps(task["current_result"], ensure_ascii=False),
                json.dumps(task["error"], ensure_ascii=False) if task["error"] else None,
                task.get("claimed_by"),
                task["created_at"],
                task["updated_at"],
            ),
        )
        conn.commit()


def save_task(task: dict[str, Any]) -> None:
    task["updated_at"] = now_iso()
    with connect() as conn:
        conn.execute(
            """
            UPDATE generation_tasks
            SET status = ?, current_stage = ?, input_json = ?, stage_artifacts_json = ?,
                current_result_json = ?, error_json = ?, claimed_by = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                task["status"],
                task["current_stage"],
                json.dumps(task["input"], ensure_ascii=False),
                json.dumps(task["stages"], ensure_ascii=False),
                json.dumps(task["current_result"], ensure_ascii=False),
                json.dumps(task["error"], ensure_ascii=False) if task["error"] else None,
                task.get("claimed_by"),
                task["updated_at"],
                task["id"],
            ),
        )
        conn.commit()


def row_to_task(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "status": row["status"],
        "current_stage": row["current_stage"],
        "input": json.loads(row["input_json"]),
        "stages": json.loads(row["stage_artifacts_json"]),
        "current_result": json.loads(row["current_result_json"]),
        "error": json.loads(row["error_json"]) if row["error_json"] else None,
        "claimed_by": row["claimed_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_task(task_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM generation_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return row_to_task(row)


def claim_next_task(worker_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT * FROM generation_tasks
            WHERE status = 'queued'
            ORDER BY created_at ASC
            LIMIT 1
            """
        ).fetchone()
        task = row_to_task(row)
        if task is None:
            conn.commit()
            return None
        task["status"] = "running"
        task["claimed_by"] = worker_id
        task["updated_at"] = now_iso()
        conn.execute(
            """
            UPDATE generation_tasks
            SET status = ?, claimed_by = ?, updated_at = ?
            WHERE id = ?
            """,
            (task["status"], task["claimed_by"], task["updated_at"], task["id"]),
        )
        conn.commit()
        return task

