from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, ValidationError

from .providers import ProviderError


START_MARKER = "<WORKFLOW_JSON>"
END_MARKER = "</WORKFLOW_JSON>"


class TextWorkflowError(RuntimeError):
    pass


class MissingMarkerError(TextWorkflowError):
    pass


class InvalidJsonError(TextWorkflowError):
    pass


@dataclass
class StageExecutionFailure(RuntimeError):
    message: str
    failure_kind: str
    attempts: int
    last_raw_output: str | None = None
    retryable: bool = True


def extract_marked_json(raw_text: str) -> dict:
    start = raw_text.find(START_MARKER)
    end = raw_text.find(END_MARKER)
    if start == -1 or end == -1 or end <= start:
        raise MissingMarkerError("模型输出缺少固定 JSON 标记")

    content = raw_text[start + len(START_MARKER) : end].strip()
    if not content:
        raise InvalidJsonError("固定 JSON 标记中没有内容")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InvalidJsonError(f"JSON 解析失败: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise InvalidJsonError("阶段 JSON 顶层必须是对象")
    return payload


def truncate_raw_output(raw_text: str | None, limit: int = 1600) -> str | None:
    if raw_text is None:
        return None
    normalized = raw_text.strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def _validate_payload(schema: type[BaseModel], payload: dict) -> dict:
    try:
        return schema.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise StageExecutionFailure(
            message=f"Schema 校验失败: {exc.errors()[0]['msg']}",
            failure_kind="schema_validation",
            attempts=0,
        ) from exc


def execute_stage_text(
    *,
    schema: type[BaseModel],
    prompt: str,
    text_runner: Callable[[str], str],
    max_attempts: int = 3,
) -> dict:
    last_raw_output: str | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            raw_text = text_runner(prompt)
            last_raw_output = truncate_raw_output(raw_text)
            payload = extract_marked_json(raw_text)
            return _validate_payload(schema, payload)
        except ProviderError as exc:
            if attempt >= max_attempts:
                raise StageExecutionFailure(
                    message=str(exc),
                    failure_kind="provider_error",
                    attempts=attempt,
                    last_raw_output=last_raw_output,
                ) from exc
        except MissingMarkerError as exc:
            if attempt >= max_attempts:
                raise StageExecutionFailure(
                    message=str(exc),
                    failure_kind="missing_marker",
                    attempts=attempt,
                    last_raw_output=last_raw_output,
                ) from exc
        except InvalidJsonError as exc:
            if attempt >= max_attempts:
                raise StageExecutionFailure(
                    message=str(exc),
                    failure_kind="invalid_json",
                    attempts=attempt,
                    last_raw_output=last_raw_output,
                ) from exc
        except StageExecutionFailure as exc:
            if attempt >= max_attempts:
                raise StageExecutionFailure(
                    message=exc.message,
                    failure_kind=exc.failure_kind,
                    attempts=attempt,
                    last_raw_output=last_raw_output,
                ) from exc
        except Exception as exc:  # noqa: BLE001
            if attempt >= max_attempts:
                raise StageExecutionFailure(
                    message=f"未预期错误: {exc}",
                    failure_kind="unexpected_error",
                    attempts=attempt,
                    last_raw_output=last_raw_output,
                ) from exc

    raise StageExecutionFailure(
        message="阶段执行失败",
        failure_kind="unexpected_error",
        attempts=max_attempts,
        last_raw_output=last_raw_output,
    )
