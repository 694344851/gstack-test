from __future__ import annotations

import time
from typing import Any, Callable

from .db import get_task, save_task
from .providers import (
    ProviderError,
    audio_render_provider,
    composition_brief_provider,
    cover_direction_provider,
    lyric_plan_provider,
    source_analysis_provider,
)


STAGES = [
    "source_analysis",
    "lyric_plan",
    "composition_brief",
    "cover_direction",
    "audio_render",
]

StageProvider = Callable[[dict[str, Any]], dict[str, Any]]


def build_empty_stages() -> dict[str, dict[str, Any]]:
    return {stage: {"status": "not_started", "artifact": None} for stage in STAGES}


def build_empty_result() -> dict[str, Any]:
    return {
        "title": None,
        "coverUrl": None,
        "audioUrl": None,
        "activeStyle": "default",
    }


def build_task(task_id: str, title: str, synopsis: str | None) -> dict[str, Any]:
    from .db import now_iso

    timestamp = now_iso()
    return {
        "id": task_id,
        "status": "queued",
        "current_stage": STAGES[0],
        "input": {"title": title, "synopsis": synopsis},
        "stages": build_empty_stages(),
        "current_result": build_empty_result(),
        "error": None,
        "claimed_by": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _set_stage_state(task: dict[str, Any], stage: str, status: str, artifact: dict[str, Any] | None = None) -> None:
    task["stages"][stage] = {"status": status, "artifact": artifact}


def _merge_result(task: dict[str, Any], stage: str, artifact: dict[str, Any]) -> None:
    if stage == "composition_brief":
        task["current_result"]["title"] = artifact["titleProposal"]
    elif stage == "cover_direction":
        task["current_result"]["coverUrl"] = artifact["coverUrl"]
        task["current_result"]["title"] = artifact["titleLock"]
    elif stage == "audio_render":
        task["current_result"]["audioUrl"] = artifact["audioUrl"]
        task["current_result"]["title"] = artifact["title"]


def _run_stage(task: dict[str, Any], stage: str) -> dict[str, Any]:
    source_artifact = task["stages"]["source_analysis"]["artifact"]
    lyric_artifact = task["stages"]["lyric_plan"]["artifact"]
    composition_artifact = task["stages"]["composition_brief"]["artifact"]
    task_input = task["input"]

    if stage == "source_analysis":
        return source_analysis_provider(task_input)
    if stage == "lyric_plan":
        return lyric_plan_provider(task_input, source_artifact)
    if stage == "composition_brief":
        return composition_brief_provider(task_input, lyric_artifact)
    if stage == "cover_direction":
        return cover_direction_provider(task_input, composition_artifact)
    if stage == "audio_render":
        return audio_render_provider(task_input, composition_artifact, lyric_artifact)
    raise ProviderError(f"Unknown stage: {stage}")


def retry_task(task_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError("Task not found")
    failed_stage = task["current_stage"]
    reset = False
    for stage in STAGES:
        if stage == failed_stage:
            reset = True
        if reset:
            task["stages"][stage] = {"status": "not_started", "artifact": None}
    task["error"] = None
    task["status"] = "queued"
    task["claimed_by"] = None
    save_task(task)
    return task


def run_task(task_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found")

    for stage in STAGES:
        stage_state = task["stages"][stage]["status"]
        if stage_state == "succeeded":
            continue
        task["current_stage"] = stage
        _set_stage_state(task, stage, "running")
        save_task(task)
        time.sleep(0.15)
        try:
            artifact = _run_stage(task, stage)
            _set_stage_state(task, stage, "succeeded", artifact)
            _merge_result(task, stage, artifact)
            task["error"] = None
            task["status"] = "running"
            save_task(task)
        except Exception as exc:  # noqa: BLE001
            _set_stage_state(task, stage, "failed", None)
            task["status"] = "failed"
            task["error"] = {
                "stage": stage,
                "message": str(exc),
                "retryable": True,
            }
            save_task(task)
            return task

    task["current_stage"] = "completed"
    task["status"] = "completed"
    task["error"] = None
    save_task(task)
    return task

