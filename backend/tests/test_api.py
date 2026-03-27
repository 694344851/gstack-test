from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _configure_app(tmp_path: Path):
    os.environ["GSTACK_TEST_DB_PATH"] = str(tmp_path / "test.db")
    from app.db import connect, create_task_row, get_task, init_db
    from app.main import (
        CreateTaskRequest,
        RenameWorkRequest,
        create_generation_task,
        delete_library_work,
        get_generation_task,
        get_library_trash,
        get_library_work,
        get_library_works,
        patch_library_work,
        restore_library_work_route,
        retry_generation_task,
        trash_library_work,
    )
    from app.orchestrator import build_task

    init_db()
    return {
        "CreateTaskRequest": CreateTaskRequest,
        "RenameWorkRequest": RenameWorkRequest,
        "build_task": build_task,
        "connect": connect,
        "create_generation_task": create_generation_task,
        "create_task_row": create_task_row,
        "delete_library_work": delete_library_work,
        "get_generation_task": get_generation_task,
        "get_library_trash": get_library_trash,
        "get_library_work": get_library_work,
        "get_library_works": get_library_works,
        "get_task": get_task,
        "patch_library_work": patch_library_work,
        "restore_library_work_route": restore_library_work_route,
        "retry_generation_task": retry_generation_task,
        "trash_library_work": trash_library_work,
    }


def _completed_task(build_task, task_id: str, source_title: str, *, created_at: str, deleted_at: str | None = None):
    task = build_task(task_id, source_title, None)
    task["status"] = "completed"
    task["current_stage"] = "completed"
    task["created_at"] = created_at
    task["updated_at"] = deleted_at or created_at
    task["stages"]["source_analysis"] = {
        "status": "succeeded",
        "artifact": {"summary": f"{source_title} 的主题摘要"},
    }
    task["stages"]["lyric_plan"] = {
        "status": "succeeded",
        "artifact": {"concept": f"{source_title} 的副歌方向"},
    }
    task["stages"]["composition_brief"] = {
        "status": "succeeded",
        "artifact": {"bpm": 96, "key": "D Minor"},
    }
    task["stages"]["cover_direction"] = {
        "status": "succeeded",
        "artifact": {
            "artDirection": f"{source_title} 的封面方向",
            "titleLock": f"{source_title}·封面版",
            "coverUrl": f"https://example.com/{task_id}.jpg",
        },
    }
    task["stages"]["audio_render"] = {
        "status": "succeeded",
        "artifact": {
            "title": f"{source_title}·音频版",
            "audioUrl": f"https://example.com/{task_id}.mp3",
            "durationSeconds": 24,
        },
    }
    task["current_result"] = {
        "title": f"{source_title}·作品版",
        "coverUrl": f"https://example.com/{task_id}.jpg",
        "audioUrl": f"https://example.com/{task_id}.mp3",
        "activeStyle": "电影流行",
    }
    task["is_trashed"] = bool(deleted_at)
    task["deleted_at"] = deleted_at
    return task


def test_init_db_backfills_trash_columns_for_existing_db(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    os.environ["GSTACK_TEST_DB_PATH"] = str(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE generation_tasks (
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

    from app.db import init_db

    init_db()

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(generation_tasks)").fetchall()}

    assert {"is_trashed", "deleted_at"}.issubset(columns)


def test_create_task_returns_queued_snapshot(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    payload = deps["create_generation_task"](
        deps["CreateTaskRequest"](title="哪吒", synopsis="一个反抗命运的故事")
    )

    assert payload["taskId"].startswith("task_")
    assert payload["snapshot"]["status"] == "queued"
    assert payload["snapshot"]["currentStage"] == "source_analysis"


def test_retry_requires_failed_task(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    create = deps["create_generation_task"](deps["CreateTaskRequest"](title="长安三万里", synopsis=None))

    with pytest.raises(HTTPException) as exc_info:
        deps["retry_generation_task"](create["taskId"])

    assert exc_info.value.status_code == 400


def test_get_missing_task_returns_404(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        deps["get_generation_task"]("missing")

    assert exc_info.value.status_code == 404


def test_library_works_returns_empty_list_when_no_completed_tasks(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)

    assert deps["get_library_works"]() == []
    assert deps["get_library_trash"]() == []


def test_library_works_returns_completed_cards_in_desc_order_and_excludes_trashed(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    create_task_row = deps["create_task_row"]
    build_task = deps["build_task"]

    create_task_row(
        _completed_task(
            build_task,
            "task_older",
            "老电影",
            created_at="2026-03-25T08:00:00+00:00",
        )
    )
    create_task_row(
        _completed_task(
            build_task,
            "task_newer",
            "新电影",
            created_at="2026-03-26T08:00:00+00:00",
        )
    )
    create_task_row(
        _completed_task(
            build_task,
            "task_trashed",
            "垃圾箱电影",
            created_at="2026-03-27T08:00:00+00:00",
            deleted_at="2026-03-27T09:00:00+00:00",
        )
    )
    create_task_row(build_task("task_queued", "排队电影", None))

    works = deps["get_library_works"]()

    assert [work["id"] for work in works] == ["task_newer", "task_older"]
    assert works[0]["title"] == "新电影·作品版"
    assert works[0]["sourceTitle"] == "新电影"
    assert works[0]["activeStyle"] == "电影流行"
    assert works[0]["hasAudio"] is True
    assert works[0]["deletedAt"] is None


def test_library_trash_returns_only_trashed_cards_in_deleted_order(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    create_task_row = deps["create_task_row"]
    build_task = deps["build_task"]

    create_task_row(
        _completed_task(
            build_task,
            "task_old_trash",
            "旧垃圾箱电影",
            created_at="2026-03-24T08:00:00+00:00",
            deleted_at="2026-03-25T08:00:00+00:00",
        )
    )
    create_task_row(
        _completed_task(
            build_task,
            "task_new_trash",
            "新垃圾箱电影",
            created_at="2026-03-23T08:00:00+00:00",
            deleted_at="2026-03-26T08:00:00+00:00",
        )
    )
    create_task_row(
        _completed_task(
            build_task,
            "task_active",
            "正常电影",
            created_at="2026-03-27T08:00:00+00:00",
        )
    )

    works = deps["get_library_trash"]()

    assert [work["id"] for work in works] == ["task_new_trash", "task_old_trash"]
    assert works[0]["deletedAt"] == "2026-03-26T08:00:00+00:00"


def test_library_works_skips_malformed_completed_rows(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    deps = _configure_app(tmp_path)
    valid = _completed_task(
        deps["build_task"],
        "task_valid",
        "流浪地球",
        created_at="2026-03-26T08:00:00+00:00",
    )
    deps["create_task_row"](valid)

    broken = _completed_task(
        deps["build_task"],
        "task_broken",
        "坏数据电影",
        created_at="2026-03-25T08:00:00+00:00",
    )
    deps["create_task_row"](broken)
    with deps["connect"]() as conn:
        conn.execute(
            "UPDATE generation_tasks SET current_result_json = ? WHERE id = ?",
            ('{"title":"坏数据"}', "task_broken"),
        )
        conn.commit()

    works = deps["get_library_works"]()

    assert [work["id"] for work in works] == ["task_valid"]
    assert "Skipping malformed library work for task task_broken" in caplog.text


def test_library_work_detail_returns_detail_dto_for_active_and_trashed_work(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    active = _completed_task(
        deps["build_task"],
        "task_active",
        "正常电影",
        created_at="2026-03-26T08:00:00+00:00",
    )
    trashed = _completed_task(
        deps["build_task"],
        "task_trashed",
        "垃圾箱电影",
        created_at="2026-03-25T08:00:00+00:00",
        deleted_at="2026-03-26T09:00:00+00:00",
    )
    deps["create_task_row"](active)
    deps["create_task_row"](trashed)

    detail = deps["get_library_work"]("task_active")
    trash_detail = deps["get_library_work"]("task_trashed")

    assert detail["id"] == "task_active"
    assert detail["title"] == "正常电影·作品版"
    assert detail["sourceTitle"] == "正常电影"
    assert detail["isTrashed"] is False
    assert detail["currentResult"]["title"] == "正常电影·作品版"
    assert detail["stages"]["audio_render"]["artifact"]["title"] == "正常电影·音频版"
    assert trash_detail["isTrashed"] is True
    assert trash_detail["deletedAt"] == "2026-03-26T09:00:00+00:00"


def test_library_work_detail_returns_404_for_missing_or_non_completed_task(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    deps["create_task_row"](deps["build_task"]("task_queued", "排队电影", None))

    with pytest.raises(HTTPException) as missing_exc:
        deps["get_library_work"]("missing")
    with pytest.raises(HTTPException) as queued_exc:
        deps["get_library_work"]("task_queued")

    assert missing_exc.value.status_code == 404
    assert queued_exc.value.status_code == 404


def test_patch_library_work_renames_active_work_and_preserves_stage_artifact_title(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    deps["create_task_row"](
        _completed_task(
            deps["build_task"],
            "task_active",
            "正常电影",
            created_at="2026-03-26T08:00:00+00:00",
        )
    )

    renamed = deps["patch_library_work"]("task_active", deps["RenameWorkRequest"](title="新的展示标题"))
    cards = deps["get_library_works"]()
    stored = deps["get_task"]("task_active")

    assert renamed["title"] == "新的展示标题"
    assert renamed["currentResult"]["title"] == "新的展示标题"
    assert renamed["stages"]["audio_render"]["artifact"]["title"] == "正常电影·音频版"
    assert cards[0]["title"] == "新的展示标题"
    assert stored["current_result"]["title"] == "新的展示标题"


def test_patch_library_work_rejects_blank_or_trashed_work(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    deps["create_task_row"](
        _completed_task(
            deps["build_task"],
            "task_trashed",
            "垃圾箱电影",
            created_at="2026-03-26T08:00:00+00:00",
            deleted_at="2026-03-26T09:00:00+00:00",
        )
    )

    with pytest.raises(HTTPException) as blank_exc:
        deps["patch_library_work"]("task_trashed", deps["RenameWorkRequest"](title="   "))
    with pytest.raises(HTTPException) as trashed_exc:
        deps["patch_library_work"]("task_trashed", deps["RenameWorkRequest"](title="改不了"))

    assert blank_exc.value.status_code == 400
    assert trashed_exc.value.status_code == 400


def test_trash_restore_and_permanent_delete_flow(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    deps["create_task_row"](
        _completed_task(
            deps["build_task"],
            "task_active",
            "正常电影",
            created_at="2026-03-26T08:00:00+00:00",
        )
    )

    trashed = deps["trash_library_work"]("task_active")
    assert trashed["isTrashed"] is True
    assert deps["get_library_works"]() == []
    assert [work["id"] for work in deps["get_library_trash"]()] == ["task_active"]

    restored = deps["restore_library_work_route"]("task_active")
    assert restored["isTrashed"] is False
    assert [work["id"] for work in deps["get_library_works"]()] == ["task_active"]
    assert deps["get_library_trash"]() == []

    deps["trash_library_work"]("task_active")
    deleted = deps["delete_library_work"]("task_active")
    assert deleted == {"ok": True}

    with pytest.raises(HTTPException) as exc_info:
        deps["get_library_work"]("task_active")

    assert exc_info.value.status_code == 404


def test_invalid_trash_restore_delete_states_return_400(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    deps["create_task_row"](
        _completed_task(
            deps["build_task"],
            "task_active",
            "正常电影",
            created_at="2026-03-26T08:00:00+00:00",
        )
    )

    with pytest.raises(HTTPException) as restore_exc:
        deps["restore_library_work_route"]("task_active")
    with pytest.raises(HTTPException) as delete_exc:
        deps["delete_library_work"]("task_active")

    assert restore_exc.value.status_code == 400
    assert delete_exc.value.status_code == 400

    deps["trash_library_work"]("task_active")
    with pytest.raises(HTTPException) as trash_again_exc:
        deps["trash_library_work"]("task_active")

    assert trash_again_exc.value.status_code == 400
