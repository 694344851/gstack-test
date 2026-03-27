from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import create_task_row, get_task, init_db
from .library_service import (
    InvalidLibraryWorkPayloadError,
    InvalidLibraryWorkStateError,
    LibraryWorkNotFoundError,
    get_library_work_detail,
    list_active_library_cards,
    list_trashed_library_cards,
    move_library_work_to_trash,
    permanently_delete_library_work,
    rename_library_work,
    restore_library_work,
)
from .orchestrator import build_task, retry_task


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    synopsis: str | None = Field(default=None, max_length=500)


class RenameWorkRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Movie to Song Workspace API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def serialize_task(task: dict) -> dict:
    # 数据库存的是 snake_case，但前端接口统一返回 camelCase。
    return {
        "id": task["id"],
        "status": task["status"],
        "currentStage": task["current_stage"],
        "input": task["input"],
        "stages": task["stages"],
        "currentResult": task["current_result"],
        "error": task["error"],
        "createdAt": task["created_at"],
        "updatedAt": task["updated_at"],
    }


def _raise_library_error(exc: Exception) -> None:
    if isinstance(exc, LibraryWorkNotFoundError):
        raise HTTPException(status_code=404, detail=exc.message) from exc
    if isinstance(exc, InvalidLibraryWorkStateError):
        raise HTTPException(status_code=400, detail=exc.message) from exc
    if isinstance(exc, InvalidLibraryWorkPayloadError):
        raise HTTPException(status_code=500, detail=exc.message) from exc
    raise exc


@app.post("/generation-tasks")
def create_generation_task(payload: CreateTaskRequest) -> dict:
    task_id = f"task_{uuid4().hex[:10]}"
    # 创建接口只负责落库一个初始任务；
    # 真正逐步执行创作流程的是后台 worker。
    task = build_task(task_id, payload.title.strip(), payload.synopsis)
    create_task_row(task)
    return {"taskId": task_id, "snapshot": serialize_task(task)}


@app.get("/generation-tasks/{task_id}")
def get_generation_task(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return serialize_task(task)


@app.get("/library/works")
def get_library_works() -> list[dict]:
    # 作品库页只需要卡片摘要，不返回完整任务快照。
    return list_active_library_cards()


@app.get("/library/works/{task_id}")
def get_library_work(task_id: str) -> dict:
    try:
        return get_library_work_detail(task_id)
    except Exception as exc:  # noqa: BLE001
        _raise_library_error(exc)


@app.patch("/library/works/{task_id}")
def patch_library_work(task_id: str, payload: RenameWorkRequest) -> dict:
    try:
        return rename_library_work(task_id, payload.title)
    except Exception as exc:  # noqa: BLE001
        _raise_library_error(exc)


@app.post("/library/works/{task_id}/trash")
def trash_library_work(task_id: str) -> dict:
    try:
        return move_library_work_to_trash(task_id)
    except Exception as exc:  # noqa: BLE001
        _raise_library_error(exc)


@app.post("/library/works/{task_id}/restore")
def restore_library_work_route(task_id: str) -> dict:
    try:
        return restore_library_work(task_id)
    except Exception as exc:  # noqa: BLE001
        _raise_library_error(exc)


@app.delete("/library/works/{task_id}")
def delete_library_work(task_id: str) -> dict:
    try:
        permanently_delete_library_work(task_id)
    except Exception as exc:  # noqa: BLE001
        _raise_library_error(exc)
    return {"ok": True}


@app.get("/library/trash")
def get_library_trash() -> list[dict]:
    return list_trashed_library_cards()


@app.post("/generation-tasks/{task_id}/retry")
def retry_generation_task(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "failed":
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")
    return serialize_task(retry_task(task_id))
