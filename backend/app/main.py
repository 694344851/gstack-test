from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import create_task_row, get_task, init_db, list_library_works
from .orchestrator import build_task, retry_task


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    synopsis: str | None = Field(default=None, max_length=500)


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


def serialize_library_work(work: dict) -> dict:
    return {
        "id": work["id"],
        "title": work["title"],
        "coverUrl": work["cover_url"],
        "sourceTitle": work["source_title"],
        "createdAt": work["created_at"],
        "activeStyle": work["active_style"],
        "hasAudio": work["has_audio"],
    }


@app.post("/generation-tasks")
def create_generation_task(payload: CreateTaskRequest) -> dict:
    task_id = f"task_{uuid4().hex[:10]}"
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
    return [serialize_library_work(work) for work in list_library_works()]


@app.post("/generation-tasks/{task_id}/retry")
def retry_generation_task(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "failed":
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")
    return serialize_task(retry_task(task_id))
