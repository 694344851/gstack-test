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
    from app.db import claim_next_task, connect, create_task_row, get_task, init_db
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
    from app.orchestrator import build_task, run_task

    init_db()
    return {
        "CreateTaskRequest": CreateTaskRequest,
        "RenameWorkRequest": RenameWorkRequest,
        "build_task": build_task,
        "claim_next_task": claim_next_task,
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
        "run_task": run_task,
        "trash_library_work": trash_library_work,
    }


def _completed_task(
    build_task,
    task_id: str,
    source_title: str,
    *,
    created_at: str,
    deleted_at: str | None = None,
    with_media: bool = False,
):
    task = build_task(task_id, source_title, None)
    task["status"] = "completed"
    task["current_stage"] = "completed"
    task["created_at"] = created_at
    task["updated_at"] = deleted_at or created_at
    task["stages"]["source_analysis"] = {
        "status": "succeeded",
        "artifact": {
            "summary": f"{source_title} 的主题摘要",
            "coreConflict": f"{source_title} 的核心冲突",
            "themes": ["反抗命运", "关系张力"],
            "emotionArc": ["压抑", "爆发"],
            "motifs": ["夜色", "火光"],
            "audienceLens": "面向喜欢电影流行的听众。",
            "lyricFocus": f"{source_title} 的副歌要落在不认命的宣告上。",
        },
    }
    task["stages"]["lyric_plan"] = {
        "status": "succeeded",
        "artifact": {
            "concept": f"{source_title} 的副歌方向",
            "narrativePOV": "第一人称",
            "sections": [
                {
                    "name": "主歌 A",
                    "purpose": "交代压力",
                    "emotionalBeat": "克制",
                    "imagery": ["夜路"],
                }
            ],
            "hook": f"{source_title} 不认命",
            "keyLines": [f"{source_title} 的关键句 1", f"{source_title} 的关键句 2"],
            "chorusDraft": [f"{source_title} 的副歌 1", f"{source_title} 的副歌 2"],
            "languageStyle": "电影流行",
            "forComposition": "副歌需要上扬空间。",
        },
    }
    task["stages"]["composition_brief"] = {
        "status": "succeeded",
        "artifact": {
            "titleProposal": f"{source_title}·作品版",
            "tempo": "96 BPM",
            "key": "D Minor",
            "timeSignature": "4/4",
            "arrangement": ["低鼓", "弦乐"],
            "vocalDirection": "主歌克制，副歌前推。",
            "sectionDynamics": [{"section": "副歌", "dynamic": "释放"}],
            "mixMood": "电影流行",
        },
    }
    task["stages"]["cover_direction"] = {
        "status": "succeeded",
        "artifact": {
            "coverTitle": f"{source_title}·封面版",
            "visualConcept": f"{source_title} 的封面方向",
            "composition": "主体偏下构图",
            "palette": ["深海蓝", "琥珀金"],
            "subjectFocus": "人物轮廓",
            "negativeSpace": "上方留白",
            "renderPrompt": "cinematic cover",
            "avoid": ["卡通感"],
        },
    }
    task["stages"]["audio_render"] = {
        "status": "succeeded",
        "artifact": {
            "versionTitle": f"{source_title}·音频版",
            "performanceDirection": f"{source_title} 的演唱说明",
            "instrumentation": ["低鼓", "弦乐"],
            "chorusLift": "副歌抬升",
            "introDirection": "前奏压抑",
            "endingDirection": "尾段延长",
            "productionNotes": ["保留颗粒感"],
            "renderPrompt": "cinematic vocal brief",
        },
    }
    task["current_result"] = {
        "title": f"{source_title}·作品版",
        "coverUrl": f"https://example.com/{task_id}.jpg" if with_media else None,
        "audioUrl": f"https://example.com/{task_id}.mp3" if with_media else None,
        "activeStyle": "电影流行",
        "currentHighlight": f"{source_title} 的当前摘要句。",
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


def test_claim_next_task_claims_oldest_queued_task_once(tmp_path: Path) -> None:
    deps = _configure_app(tmp_path)
    build_task = deps["build_task"]

    older = build_task("task_older", "???", None)
    older["created_at"] = "2026-03-25T08:00:00+00:00"
    older["updated_at"] = older["created_at"]
    newer = build_task("task_newer", "???", None)
    newer["created_at"] = "2026-03-26T08:00:00+00:00"
    newer["updated_at"] = newer["created_at"]

    deps["create_task_row"](newer)
    deps["create_task_row"](older)

    first = deps["claim_next_task"]("worker-a")
    second = deps["claim_next_task"]("worker-b")
    exhausted = deps["claim_next_task"]("worker-c")

    assert first is not None
    assert first["id"] == "task_older"
    assert first["status"] == "running"
    assert first["claimed_by"] == "worker-a"

    assert second is not None
    assert second["id"] == "task_newer"
    assert second["claimed_by"] == "worker-b"

    assert exhausted is None


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
    assert works[0]["currentHighlight"] == "新电影 的当前摘要句。"
    assert works[0]["coverUrl"] is None
    assert works[0]["hasAudio"] is False
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
    assert detail["currentHighlight"] == "正常电影 的当前摘要句。"
    assert detail["stages"]["audio_render"]["artifact"]["versionTitle"] == "正常电影·音频版"
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
    assert renamed["stages"]["audio_render"]["artifact"]["versionTitle"] == "正常电影·音频版"
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


def test_run_task_completes_all_text_stages_with_mocked_text_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps = _configure_app(tmp_path)

    task = deps["build_task"]("task_stub", "白蛇", "一段关于命运与选择的故事")
    deps["create_task_row"](task)

    import app.orchestrator as orchestrator

    responses = {
        "source_analysis": """
<WORKFLOW_JSON>
{"summary":"《白蛇》被提炼成一条从压抑到宣告的情绪上升线。","coreConflict":"主角在宿命压迫与自我选择之间不断拉扯。","themes":["反抗命运","关系牵引","自我宣告"],"emotionArc":["压抑","试探","抬升","爆发"],"motifs":["夜色","火光","逆风","回声"],"audienceLens":"适合期待强副歌和电影感叙事的流行听众。","lyricFocus":"把“我不认命”的内心转折写成可被合唱放大的副歌核心。"}
</WORKFLOW_JSON>
""".strip(),
        "lyric_plan": """
<WORKFLOW_JSON>
{"concept":"围绕《白蛇》的命运对抗写一首先压抑后宣告的电影流行歌。","narrativePOV":"第一人称，贴近主角在压力边缘的自白。","sections":[{"name":"主歌 A","purpose":"交代命运压力和被逼到边缘的处境。","emotionalBeat":"克制而发紧","imagery":["夜路","余烬"]},{"name":"预副歌","purpose":"把情绪从忍耐推到临界点。","emotionalBeat":"拉升与决断","imagery":["风口","回声"]},{"name":"副歌","purpose":"给出不认命的核心宣告。","emotionalBeat":"开阔爆发","imagery":["火光","逆风"]}],"hook":"命可以压我一程，压不灭我这口气。","keyLines":["我把沉默熬成一声反击","逆着风也要把名字唱清"],"chorusDraft":["命可以压我一程 压不灭我这口气","就算夜把路吹散 我也要迎着火光去"],"languageStyle":"口语化但有电影感，短句利于副歌齐唱。","forComposition":"主歌保留留白，副歌需要更大旋律上扬和群唱空间。"}
</WORKFLOW_JSON>
""".strip(),
        "composition_brief": """
<WORKFLOW_JSON>
{"titleProposal":"白蛇·逆光版","tempo":"92 BPM","key":"D Minor","timeSignature":"4/4","arrangement":["低鼓脉冲","弦乐铺底","合成器氛围","副歌叠唱"],"vocalDirection":"主歌压着唱，预副歌前推，副歌释放并加厚和声。","sectionDynamics":[{"section":"主歌 A","dynamic":"低密度，保留空隙"},{"section":"预副歌","dynamic":"鼓点抬升，张力聚集"},{"section":"副歌","dynamic":"频宽拉满，情绪释放"}],"mixMood":"冷色底盘里保留一点热感冲顶，强调电影流行的推背感。"}
</WORKFLOW_JSON>
""".strip(),
        "cover_direction": """
<WORKFLOW_JSON>
{"coverTitle":"白蛇·逆光版","visualConcept":"在冷色深夜中保留一束热光，像命运压迫下仍然点亮的意志。","composition":"主体偏下构图，光源从画面一角切入，保留上方负空间。","palette":["深海蓝","炭黑","琥珀金"],"subjectFocus":"一个迎着逆风站定的人物轮廓。","negativeSpace":"上方留出大面积暗部，让标题和情绪有呼吸位。","renderPrompt":"cinematic single cover, deep blue night, amber rim light, lone silhouette facing headwind","avoid":["卡通感","过度赛博","拥挤背景"]}
</WORKFLOW_JSON>
""".strip(),
        "audio_render": """
<WORKFLOW_JSON>
{"versionTitle":"白蛇·导演说明版","performanceDirection":"主歌像压住情绪的自白，副歌必须唱出宣告感和群体共振。","instrumentation":["低鼓","弦乐","铺底合成器","副歌群唱"],"chorusLift":"副歌首句立刻抬八度区间，鼓和和声同时加厚。","introDirection":"前奏用稀薄氛围和低频脉冲先建立压迫感。","endingDirection":"尾段保留一拍空白后收在长音，让宣告感悬停。","productionNotes":["保留人声颗粒感","副歌低频不要过满","避免 EDM 式过度堆叠"],"renderPrompt":"female/male pop vocal with cinematic chorus lift, restrained verse, anthemic hook, emotional climax"}
</WORKFLOW_JSON>
""".strip(),
    }

    monkeypatch.setattr(orchestrator, "call_stage_text", lambda stage, prompt: responses[stage])

    result = deps["run_task"]("task_stub")

    assert result["status"] == "completed"
    assert result["current_stage"] == "completed"
    assert all(result["stages"][stage]["status"] == "succeeded" for stage in result["stages"])
    assert result["current_result"]["title"] == "白蛇·导演说明版"
    assert result["current_result"]["coverUrl"] is None
    assert result["current_result"]["audioUrl"] is None
    assert isinstance(result["current_result"]["currentHighlight"], str)


def test_run_task_persists_structured_failure_after_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps = _configure_app(tmp_path)
    task = deps["build_task"]("task_fail", "封神", None)
    deps["create_task_row"](task)

    import app.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "call_stage_text", lambda stage, prompt: "plain text without markers")

    result = deps["run_task"]("task_fail")

    assert result["status"] == "failed"
    assert result["current_stage"] == "source_analysis"
    assert result["error"]["failureKind"] == "missing_marker"
    assert result["error"]["attempts"] == 3
    assert "plain text without markers" in result["error"]["lastRawOutput"]


def test_retry_endpoint_preserves_upstream_artifacts_and_clears_downstream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps = _configure_app(tmp_path)
    task = deps["build_task"]("task_retry", "哪吒", None)
    deps["create_task_row"](task)

    import app.orchestrator as orchestrator

    def fake_call(stage: str, prompt: str) -> str:
        if stage == "source_analysis":
            return """
<WORKFLOW_JSON>
{"summary":"摘要","coreConflict":"冲突","themes":["反抗"],"emotionArc":["压抑"],"motifs":["火光"],"audienceLens":"大众流行","lyricFocus":"副歌聚焦宣告"}
</WORKFLOW_JSON>
""".strip()
        if stage == "lyric_plan":
            return """
<WORKFLOW_JSON>
{"concept":"歌词方向","narrativePOV":"第一人称","sections":[{"name":"主歌 A","purpose":"铺垫","emotionalBeat":"克制","imagery":["夜路"]}],"hook":"不认命","keyLines":["句子一","句子二"],"chorusDraft":["副歌一","副歌二"],"languageStyle":"电影流行","forComposition":"副歌上扬"}
</WORKFLOW_JSON>
""".strip()
        return "broken"

    monkeypatch.setattr(orchestrator, "call_stage_text", fake_call)

    failed = deps["run_task"]("task_retry")
    assert failed["status"] == "failed"
    assert failed["current_stage"] == "composition_brief"

    retried = deps["retry_generation_task"]("task_retry")

    assert retried["stages"]["source_analysis"]["status"] == "succeeded"
    assert retried["stages"]["lyric_plan"]["status"] == "succeeded"
    assert retried["stages"]["composition_brief"]["status"] == "not_started"
    assert retried["stages"]["cover_direction"]["status"] == "not_started"
    assert retried["stages"]["audio_render"]["status"] == "not_started"
