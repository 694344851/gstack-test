from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .db import (
    delete_task_row,
    get_task,
    list_library_works,
    list_trashed_library_works,
    mark_task_trashed,
    now_iso,
    restore_trashed_task,
    save_task,
)


@dataclass
class LibraryServiceError(Exception):
    message: str


@dataclass
class LibraryWorkNotFoundError(LibraryServiceError):
    message: str = "Work not found"


@dataclass
class InvalidLibraryWorkStateError(LibraryServiceError):
    message: str


@dataclass
class InvalidLibraryWorkPayloadError(LibraryServiceError):
    message: str


def _validate_completed_task(task_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None or task["status"] != "completed":
        raise LibraryWorkNotFoundError()
    if not isinstance(task["input"], dict) or not isinstance(task["current_result"], dict):
        raise InvalidLibraryWorkPayloadError("Malformed work payload")
    return task


def _serialize_library_card(work: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": work["id"],
        "title": work["title"],
        "coverUrl": work["cover_url"],
        "sourceTitle": work["source_title"],
        "createdAt": work["created_at"],
        "activeStyle": work["active_style"],
        "hasAudio": work["has_audio"],
        "deletedAt": work["deleted_at"],
    }


def _serialize_detail(task: dict[str, Any]) -> dict[str, Any]:
    current_result = task["current_result"]
    task_input = task["input"]

    title = current_result.get("title")
    if not isinstance(title, str) or not title.strip():
        raise InvalidLibraryWorkPayloadError("Malformed work title")

    return {
        "id": task["id"],
        "title": title,
        "coverUrl": current_result.get("coverUrl"),
        "sourceTitle": task_input.get("title"),
        "createdAt": task["created_at"],
        "updatedAt": task["updated_at"],
        "activeStyle": current_result.get("activeStyle"),
        "hasAudio": bool(current_result.get("audioUrl")),
        "isTrashed": task["is_trashed"],
        "deletedAt": task["deleted_at"],
        "input": task_input,
        "stages": task["stages"],
        "currentResult": current_result,
    }


def list_active_library_cards() -> list[dict[str, Any]]:
    return [_serialize_library_card(work) for work in list_library_works()]


def list_trashed_library_cards() -> list[dict[str, Any]]:
    return [_serialize_library_card(work) for work in list_trashed_library_works()]


def get_library_work_detail(task_id: str) -> dict[str, Any]:
    task = _validate_completed_task(task_id)
    return _serialize_detail(task)


def rename_library_work(task_id: str, title: str) -> dict[str, Any]:
    trimmed_title = title.strip()
    if not trimmed_title:
        raise InvalidLibraryWorkStateError("Title cannot be empty")

    task = _validate_completed_task(task_id)
    if task["is_trashed"]:
        raise InvalidLibraryWorkStateError("Cannot rename a trashed work")

    current_result = task["current_result"]
    current_result["title"] = trimmed_title
    save_task(task)
    return _serialize_detail(task)


def move_library_work_to_trash(task_id: str) -> dict[str, Any]:
    task = _validate_completed_task(task_id)
    if task["is_trashed"]:
        raise InvalidLibraryWorkStateError("Work is already in trash")

    deleted_at = now_iso()
    mark_task_trashed(task_id, deleted_at)
    task = _validate_completed_task(task_id)
    return _serialize_detail(task)


def restore_library_work(task_id: str) -> dict[str, Any]:
    task = _validate_completed_task(task_id)
    if not task["is_trashed"]:
        raise InvalidLibraryWorkStateError("Work is not in trash")

    restore_trashed_task(task_id, now_iso())
    task = _validate_completed_task(task_id)
    return _serialize_detail(task)


def permanently_delete_library_work(task_id: str) -> None:
    task = _validate_completed_task(task_id)
    if not task["is_trashed"]:
        raise InvalidLibraryWorkStateError("Only trashed works can be permanently deleted")
    delete_task_row(task_id)
