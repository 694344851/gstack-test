from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import HTTPException


def _configure_app(tmp_path: Path):
    os.environ["GSTACK_TEST_DB_PATH"] = str(tmp_path / "test.db")
    from app.db import connect, create_task_row, init_db
    from app.main import (
        CreateTaskRequest,
        create_generation_task,
        get_generation_task,
        get_library_works,
        retry_generation_task,
    )
    from app.orchestrator import build_task

    init_db()
    return {
        "CreateTaskRequest": CreateTaskRequest,
        "build_task": build_task,
        "connect": connect,
        "create_generation_task": create_generation_task,
        "create_task_row": create_task_row,
        "get_generation_task": get_generation_task,
        "get_library_works": get_library_works,
        "retry_generation_task": retry_generation_task,
    }


def test_create_task_returns_queued_snapshot(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    CreateTaskRequest = deps["CreateTaskRequest"]
    create_generation_task = deps["create_generation_task"]
    payload = create_generation_task(CreateTaskRequest(title="哪吒", synopsis="一个反抗命运的故事"))

    assert payload["taskId"].startswith("task_")
    assert payload["snapshot"]["status"] == "queued"
    assert payload["snapshot"]["currentStage"] == "source_analysis"


def test_retry_requires_failed_task(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    CreateTaskRequest = deps["CreateTaskRequest"]
    create_generation_task = deps["create_generation_task"]
    retry_generation_task = deps["retry_generation_task"]
    create = create_generation_task(CreateTaskRequest(title="长安三万里", synopsis=None))
    task_id = create["taskId"]

    with pytest.raises(HTTPException) as exc_info:
        retry_generation_task(task_id)

    assert exc_info.value.status_code == 400


def test_get_missing_task_returns_404(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    get_generation_task = deps["get_generation_task"]

    with pytest.raises(HTTPException) as exc_info:
        get_generation_task("missing")

    assert exc_info.value.status_code == 404


def test_library_works_returns_empty_list_when_no_completed_tasks(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    get_library_works = deps["get_library_works"]

    works = get_library_works()

    assert works == []


def test_library_works_returns_completed_cards_in_desc_order(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    build_task = deps["build_task"]
    create_task_row = deps["create_task_row"]
    get_library_works = deps["get_library_works"]

    older = build_task("task_older", "老电影", None)
    older["status"] = "completed"
    older["current_stage"] = "completed"
    older["created_at"] = "2026-03-25T08:00:00+00:00"
    older["updated_at"] = older["created_at"]
    older["current_result"] = {
        "title": "老电影·夜航版",
        "coverUrl": "https://example.com/older.jpg",
        "audioUrl": None,
        "activeStyle": "电影流行",
    }
    create_task_row(older)

    newer = build_task("task_newer", "新电影", "更热的版本")
    newer["status"] = "completed"
    newer["current_stage"] = "completed"
    newer["created_at"] = "2026-03-26T08:00:00+00:00"
    newer["updated_at"] = newer["created_at"]
    newer["current_result"] = {
        "title": "新电影·霓虹版",
        "coverUrl": "https://example.com/newer.jpg",
        "audioUrl": "https://example.com/newer.mp3",
        "activeStyle": "电子流行",
    }
    create_task_row(newer)

    queued = build_task("task_queued", "排队电影", None)
    create_task_row(queued)

    works = get_library_works()

    assert [work["id"] for work in works] == ["task_newer", "task_older"]
    assert works[0]["title"] == "新电影·霓虹版"
    assert works[0]["sourceTitle"] == "新电影"
    assert works[0]["createdAt"] == "2026-03-26T08:00:00+00:00"
    assert works[0]["activeStyle"] == "电子流行"
    assert works[0]["hasAudio"] is True
    assert works[1]["hasAudio"] is False


def test_library_works_skips_malformed_completed_rows(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    deps = _configure_app(tmp_path)
    build_task = deps["build_task"]
    create_task_row = deps["create_task_row"]
    connect = deps["connect"]
    get_library_works = deps["get_library_works"]

    valid = build_task("task_valid", "流浪地球", None)
    valid["status"] = "completed"
    valid["current_stage"] = "completed"
    valid["current_result"] = {
        "title": "流浪地球·引擎版",
        "coverUrl": "https://example.com/valid.jpg",
        "audioUrl": None,
        "activeStyle": "史诗电子",
    }
    create_task_row(valid)

    broken = build_task("task_broken", "坏数据电影", None)
    broken["status"] = "completed"
    broken["current_stage"] = "completed"
    create_task_row(broken)
    with connect() as conn:
        conn.execute(
            "UPDATE generation_tasks SET current_result_json = ? WHERE id = ?",
            ('{"title":"坏数据"}', "task_broken"),
        )
        conn.commit()

    works = get_library_works()

    assert [work["id"] for work in works] == ["task_valid"]
    assert "Skipping malformed library work for task task_broken" in caplog.text
