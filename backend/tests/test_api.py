from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import HTTPException


def _configure_app(tmp_path: Path):
    os.environ["GSTACK_TEST_DB_PATH"] = str(tmp_path / "test.db")
    from app.db import init_db
    from app.main import (
        CreateTaskRequest,
        create_generation_task,
        get_generation_task,
        retry_generation_task,
    )

    init_db()
    return CreateTaskRequest, create_generation_task, get_generation_task, retry_generation_task


def test_create_task_returns_queued_snapshot(tmp_path: Path) -> None:
    CreateTaskRequest, create_generation_task, _, _ = _configure_app(tmp_path)
    payload = create_generation_task(CreateTaskRequest(title="哪吒", synopsis="一个反抗命运的故事"))

    assert payload["taskId"].startswith("task_")
    assert payload["snapshot"]["status"] == "queued"
    assert payload["snapshot"]["currentStage"] == "source_analysis"


def test_retry_requires_failed_task(tmp_path: Path) -> None:
    CreateTaskRequest, create_generation_task, _, retry_generation_task = _configure_app(tmp_path)
    create = create_generation_task(CreateTaskRequest(title="长安三万里", synopsis=None))
    task_id = create["taskId"]

    with pytest.raises(HTTPException) as exc_info:
        retry_generation_task(task_id)

    assert exc_info.value.status_code == 400


def test_get_missing_task_returns_404(tmp_path: Path) -> None:
    _, _, get_generation_task, _ = _configure_app(tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        get_generation_task("missing")

    assert exc_info.value.status_code == 404
