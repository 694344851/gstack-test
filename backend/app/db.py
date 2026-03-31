from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from sqlalchemy import (
    Column,
    Integer,
    JSON,
    String,
    create_engine,
    select,
    update,
    delete,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DB_ENV = "GSTACK_TEST_DB_PATH"
DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "app.db"
logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path() -> Path:
    return Path(os.environ.get(DB_ENV, DEFAULT_DB))


def get_engine_url() -> str:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


class Base(DeclarativeBase):
    pass


class GenerationTask(Base):
    __tablename__ = "generation_tasks"

    id = Column(String, primary_key=True)
    status = Column(String, nullable=False)
    current_stage = Column(String, nullable=False)
    input_json = Column(JSON, nullable=False)
    stage_artifacts_json = Column(JSON, nullable=False)
    current_result_json = Column(JSON, nullable=False)
    error_json = Column(JSON, nullable=True)
    claimed_by = Column(String, nullable=True)
    is_trashed = Column(Integer, nullable=False, default=0)
    deleted_at = Column(String, nullable=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


def _get_engine():
    # Create engine dynamically based on current environment variable
    return create_engine(get_engine_url(), connect_args={"check_same_thread": False})


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
                input_json JSON NOT NULL,
                stage_artifacts_json JSON NOT NULL,
                current_result_json JSON NOT NULL,
                error_json JSON,
                claimed_by TEXT,
                is_trashed INTEGER NOT NULL DEFAULT 0,
                deleted_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(generation_tasks)").fetchall()}
        if "is_trashed" not in columns:
            conn.execute("ALTER TABLE generation_tasks ADD COLUMN is_trashed INTEGER NOT NULL DEFAULT 0")
        if "deleted_at" not in columns:
            conn.execute("ALTER TABLE generation_tasks ADD COLUMN deleted_at TEXT")
        conn.commit()

    engine = _get_engine()
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    init_db()  # Ensure tables exist
    engine = _get_engine()
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def connect() -> sqlite3.Connection:
    """Legacy connect function for tests."""
    init_db()
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_task_row(task_dict: dict[str, Any]) -> None:
    with get_session() as session:
        task = GenerationTask(
            id=task_dict["id"],
            status=task_dict["status"],
            current_stage=task_dict["current_stage"],
            input_json=task_dict["input"],
            stage_artifacts_json=task_dict["stages"],
            current_result_json=task_dict["current_result"],
            error_json=task_dict["error"],
            claimed_by=task_dict.get("claimed_by"),
            is_trashed=int(bool(task_dict.get("is_trashed", False))),
            deleted_at=task_dict.get("deleted_at"),
            created_at=task_dict["created_at"],
            updated_at=task_dict["updated_at"],
        )
        session.add(task)
        session.commit()


def save_task(task_dict: dict[str, Any]) -> None:
    task_dict["updated_at"] = now_iso()
    with get_session() as session:
        stmt = (
            update(GenerationTask)
            .where(GenerationTask.id == task_dict["id"])
            .values(
                status=task_dict["status"],
                current_stage=task_dict["current_stage"],
                input_json=task_dict["input"],
                stage_artifacts_json=task_dict["stages"],
                current_result_json=task_dict["current_result"],
                error_json=task_dict["error"],
                claimed_by=task_dict.get("claimed_by"),
                updated_at=task_dict["updated_at"],
            )
        )
        session.execute(stmt)
        session.commit()


def _deserialize_json_field(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        return json.loads(value)
    raise TypeError(f"Unsupported JSON field type: {type(value)!r}")


def row_to_task(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "status": row["status"],
        "current_stage": row["current_stage"],
        "input": _deserialize_json_field(row["input_json"]),
        "stages": _deserialize_json_field(row["stage_artifacts_json"]),
        "current_result": _deserialize_json_field(row["current_result_json"]),
        "error": _deserialize_json_field(row["error_json"]),
        "claimed_by": row["claimed_by"],
        "is_trashed": bool(row["is_trashed"]),
        "deleted_at": row["deleted_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def model_to_task_dict(task: GenerationTask | None) -> dict[str, Any] | None:
    if task is None:
        return None
    return {
        "id": task.id,
        "status": task.status,
        "current_stage": task.current_stage,
        "input": task.input_json,
        "stages": task.stage_artifacts_json,
        "current_result": task.current_result_json,
        "error": task.error_json,
        "claimed_by": task.claimed_by,
        "is_trashed": bool(task.is_trashed),
        "deleted_at": task.deleted_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def get_task(task_id: str) -> dict[str, Any] | None:
    with get_session() as session:
        task = session.get(GenerationTask, task_id)
        return model_to_task_dict(task)


def _model_to_library_work(task: GenerationTask) -> dict[str, Any]:
    current_result = task.current_result_json
    task_input = task.input_json

    if not isinstance(current_result, dict) or not isinstance(task_input, dict):
        raise ValueError("task payload must be an object")

    return {
        "id": task.id,
        "title": current_result["title"],
        "cover_url": current_result.get("coverUrl"),
        "source_title": task_input["title"],
        "created_at": task.created_at,
        "active_style": current_result["activeStyle"],
        "current_highlight": current_result.get("currentHighlight"),
        "has_audio": bool(current_result.get("audioUrl")),
        "deleted_at": task.deleted_at,
    }


def list_library_works() -> list[dict[str, Any]]:
    with get_session() as session:
        stmt = (
            select(GenerationTask)
            .where(GenerationTask.status == "completed", GenerationTask.is_trashed == 0)
            .order_by(GenerationTask.created_at.desc())
        )
        tasks = session.execute(stmt).scalars().all()

        works: list[dict[str, Any]] = []
        for task in tasks:
            try:
                works.append(_model_to_library_work(task))
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping malformed library work for task %s: %s", task.id, exc)
        return works


def list_trashed_library_works() -> list[dict[str, Any]]:
    with get_session() as session:
        stmt = (
            select(GenerationTask)
            .where(GenerationTask.status == "completed", GenerationTask.is_trashed == 1)
            .order_by(GenerationTask.deleted_at.desc(), GenerationTask.created_at.desc())
        )
        tasks = session.execute(stmt).scalars().all()

        works: list[dict[str, Any]] = []
        for task in tasks:
            try:
                works.append(_model_to_library_work(task))
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping malformed trashed library work for task %s: %s", task.id, exc)
        return works


def mark_task_trashed(task_id: str, deleted_at: str) -> bool:
    with get_session() as session:
        stmt = (
            update(GenerationTask)
            .where(GenerationTask.id == task_id)
            .values(is_trashed=1, deleted_at=deleted_at, updated_at=deleted_at)
        )
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0


def restore_trashed_task(task_id: str, updated_at: str) -> bool:
    with get_session() as session:
        stmt = (
            update(GenerationTask)
            .where(GenerationTask.id == task_id)
            .values(is_trashed=0, deleted_at=None, updated_at=updated_at)
        )
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0


def delete_task_row(task_id: str) -> bool:
    with get_session() as session:
        stmt = delete(GenerationTask).where(GenerationTask.id == task_id)
        result = session.execute(stmt)
        session.commit()
        return result.rowcount > 0


def claim_next_task(worker_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        # Lock before selecting to keep multiple workers from claiming the same task.
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
