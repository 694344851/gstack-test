from __future__ import annotations

import logging
import time
from typing import Any

from .db import get_task, save_task
from .providers import (
    build_audio_render_prompt,
    build_composition_brief_prompt,
    build_cover_direction_prompt,
    build_lyric_plan_prompt,
    build_source_analysis_prompt,
    call_stage_text,
)
from .stage_schemas import (
    AudioRenderArtifact,
    CompositionBriefArtifact,
    CoverDirectionArtifact,
    LyricPlanArtifact,
    SourceAnalysisArtifact,
)
from .text_workflow import StageExecutionFailure, execute_stage_text


STAGES = [
    "source_analysis",
    "lyric_plan",
    "composition_brief",
    "cover_direction",
    "audio_render",
]
logger = logging.getLogger(__name__)


def build_empty_stages() -> dict[str, dict[str, Any]]:
    return {stage: {"status": "not_started", "artifact": None} for stage in STAGES}


def build_empty_result() -> dict[str, Any]:
    return {
        "title": None,
        "coverUrl": None,
        "audioUrl": None,
        "activeStyle": "创作工作台",
        "currentHighlight": None,
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
    current_result = task["current_result"]
    if stage == "source_analysis":
        current_result["currentHighlight"] = artifact["lyricFocus"]
    elif stage == "lyric_plan":
        current_result["activeStyle"] = artifact["languageStyle"]
        current_result["currentHighlight"] = artifact["hook"]
    elif stage == "composition_brief":
        current_result["title"] = artifact["titleProposal"]
        current_result["activeStyle"] = artifact["mixMood"]
        current_result["currentHighlight"] = artifact["vocalDirection"]
    elif stage == "cover_direction":
        current_result["title"] = artifact["coverTitle"]
        current_result["currentHighlight"] = artifact["visualConcept"]
        current_result["coverUrl"] = None
    elif stage == "audio_render":
        current_result["title"] = artifact["versionTitle"]
        current_result["currentHighlight"] = artifact["performanceDirection"]
        current_result["audioUrl"] = None


def _stage_prompt(task: dict[str, Any], stage: str) -> str:
    task_input = task["input"]
    stages = task["stages"]
    if stage == "source_analysis":
        return build_source_analysis_prompt(task_input)
    if stage == "lyric_plan":
        return build_lyric_plan_prompt(task_input, stages["source_analysis"]["artifact"])
    if stage == "composition_brief":
        return build_composition_brief_prompt(task_input, stages["lyric_plan"]["artifact"])
    if stage == "cover_direction":
        return build_cover_direction_prompt(task_input, stages["composition_brief"]["artifact"])
    if stage == "audio_render":
        return build_audio_render_prompt(
            task_input,
            stages["composition_brief"]["artifact"],
            stages["lyric_plan"]["artifact"],
        )
    raise ValueError(f"Unknown stage: {stage}")


def _stage_schema(stage: str):
    if stage == "source_analysis":
        return SourceAnalysisArtifact
    if stage == "lyric_plan":
        return LyricPlanArtifact
    if stage == "composition_brief":
        return CompositionBriefArtifact
    if stage == "cover_direction":
        return CoverDirectionArtifact
    if stage == "audio_render":
        return AudioRenderArtifact
    raise ValueError(f"Unknown stage: {stage}")


def _run_stage(task: dict[str, Any], stage: str) -> dict[str, Any]:
    prompt = _stage_prompt(task, stage)
    schema = _stage_schema(stage)
    logger.info("task=%s stage=%s prompt_prepared", task["id"], stage)
    return execute_stage_text(
        schema=schema,
        prompt=prompt,
        text_runner=lambda built_prompt: call_stage_text(stage, built_prompt),
    )


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
        if task["stages"][stage]["status"] == "succeeded":
            continue

        task["current_stage"] = stage
        _set_stage_state(task, stage, "running")
        save_task(task)
        logger.info("task=%s stage=%s started", task["id"], stage)
        time.sleep(0.15)

        try:
            artifact = _run_stage(task, stage)
            _set_stage_state(task, stage, "succeeded", artifact)
            _merge_result(task, stage, artifact)
            task["error"] = None
            task["status"] = "running"
            save_task(task)
            logger.info("task=%s stage=%s succeeded", task["id"], stage)
        except StageExecutionFailure as exc:
            _set_stage_state(task, stage, "failed", None)
            task["status"] = "failed"
            task["error"] = {
                "stage": stage,
                "message": exc.message,
                "retryable": exc.retryable,
                "attempts": exc.attempts,
                "failureKind": exc.failure_kind,
                "lastRawOutput": exc.last_raw_output,
            }
            save_task(task)
            logger.error(
                "task=%s stage=%s failed kind=%s attempts=%s message=%s",
                task["id"],
                stage,
                exc.failure_kind,
                exc.attempts,
                exc.message,
            )
            return task
        except Exception as exc:  # noqa: BLE001
            _set_stage_state(task, stage, "failed", None)
            task["status"] = "failed"
            task["error"] = {
                "stage": stage,
                "message": str(exc),
                "retryable": True,
                "attempts": 1,
                "failureKind": "unexpected_error",
                "lastRawOutput": None,
            }
            save_task(task)
            logger.exception("task=%s stage=%s unexpected_failure", task["id"], stage)
            return task

    task["current_stage"] = "completed"
    task["status"] = "completed"
    task["error"] = None
    save_task(task)
    logger.info("task=%s completed", task["id"])
    return task
