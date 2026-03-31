from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx


TEXT_API_URL_ENV = "GSTACK_TEXT_API_URL"
TEXT_API_KEY_ENV = "GSTACK_TEXT_API_KEY"
TEXT_API_MODEL_ENV = "GSTACK_TEXT_API_MODEL"
TEXT_API_REQUEST_FORMAT_ENV = "GSTACK_TEXT_API_REQUEST_FORMAT"
TEXT_API_PROMPT_FIELD_ENV = "GSTACK_TEXT_API_PROMPT_FIELD"
TEXT_API_RESPONSE_TEXT_PATH_ENV = "GSTACK_TEXT_API_RESPONSE_TEXT_PATH"
TEXT_API_TIMEOUT_ENV = "GSTACK_TEXT_API_TIMEOUT_SECONDS"
logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """Raised when a provider fails in a user-visible way."""


def _safe_title(raw: str) -> str:
    return raw.strip() or "未命名题材"


def _json_block(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _render_context(task_input: dict[str, Any], upstream: dict[str, Any] | None = None) -> str:
    blocks = [
        "输入题材:",
        _json_block(
            {
                "title": _safe_title(task_input["title"]),
                "synopsis": task_input.get("synopsis") or "",
            }
        ),
    ]
    if upstream is not None:
        blocks.extend(["上游产物:", _json_block(upstream)])
    return "\n".join(blocks)


def build_source_analysis_prompt(task_input: dict[str, Any]) -> str:
    return f"""你是一名电影题材歌曲开发流程中的剧情提炼节点。
目标：把题材整理成后续歌词策划可直接消费的专业工作台产物。

{_render_context(task_input)}

输出要求：
1. 只输出中文。
2. 只输出 <WORKFLOW_JSON> 和 </WORKFLOW_JSON> 包裹的 JSON。
3. 不要输出 markdown，不要解释，不要寒暄。
4. JSON 必须包含：
summary, coreConflict, themes, emotionArc, motifs, audienceLens, lyricFocus
5. themes、emotionArc、motifs 必须是数组。
6. 结果要服务歌词创作，不要写成影评。
"""


def build_lyric_plan_prompt(task_input: dict[str, Any], source_analysis: dict[str, Any]) -> str:
    return f"""你是一名歌词结构节点。
目标：基于剧情提炼结果，产出专业的歌词策划文档，并给出少量半成品歌词抓手。

{_render_context(task_input, source_analysis)}

输出要求：
1. 只输出中文。
2. 只输出 <WORKFLOW_JSON> 和 </WORKFLOW_JSON> 包裹的 JSON。
3. 不要输出 markdown，不要解释，不要寒暄。
4. JSON 必须包含：
concept, narrativePOV, sections, hook, keyLines, chorusDraft, languageStyle, forComposition
5. sections 必须是对象数组，每项包含：
name, purpose, emotionalBeat, imagery；其中 imagery 必须是字符串数组，不能是单个字符串。
6. keyLines 必须是至少 2 条字符串组成的数组。
7. chorusDraft 必须是至少 2 条字符串组成的数组，不能是单个长句字符串。
8. 这是整条链路的质量锚点，语言要像专业创作工作台，不要像聊天回答。
"""


def build_composition_brief_prompt(task_input: dict[str, Any], lyric_plan: dict[str, Any]) -> str:
    return f"""你是一名编曲设定节点。
目标：把歌词结构转换成音乐制作可消费的编曲 brief。

{_render_context(task_input, lyric_plan)}

输出要求：
1. 只输出中文。
2. 只输出 <WORKFLOW_JSON> 和 </WORKFLOW_JSON> 包裹的 JSON。
3. 不要输出 markdown，不要解释，不要寒暄。
4. JSON 必须包含：
titleProposal, tempo, key, timeSignature, arrangement, vocalDirection, sectionDynamics, mixMood
5. titleProposal、tempo、key、timeSignature、vocalDirection、mixMood 都必须是字符串；tempo 也必须写成字符串，例如 "92 BPM"，不要返回数字。
6. arrangement 必须是字符串数组，不能返回对象。
7. sectionDynamics 必须是对象数组，每项包含 section 和 dynamic，二者都必须是字符串。
8. 结果必须明显消费 lyric_plan，不要只给 BPM 和调式。
"""


def build_cover_direction_prompt(task_input: dict[str, Any], composition_brief: dict[str, Any]) -> str:
    return f"""你是一名封面方向节点。
目标：输出真实可用的视觉导演 brief，而不是图片链接。

{_render_context(task_input, composition_brief)}

输出要求：
1. 只输出中文。
2. 只输出 <WORKFLOW_JSON> 和 </WORKFLOW_JSON> 包裹的 JSON。
3. 不要输出 markdown，不要解释，不要寒暄。
4. JSON 必须包含：
coverTitle, visualConcept, composition, palette, subjectFocus, negativeSpace, renderPrompt, avoid
5. coverTitle、visualConcept、composition、subjectFocus、negativeSpace、renderPrompt 都必须是字符串。
6. palette 与 avoid 都必须是字符串数组，不能返回对象或单个字符串。
7. 不要返回 coverUrl。
"""


def build_audio_render_prompt(
    task_input: dict[str, Any],
    composition_brief: dict[str, Any],
    lyric_plan: dict[str, Any],
) -> str:
    upstream = {
        "composition_brief": composition_brief,
        "lyric_plan": lyric_plan,
    }
    return f"""你是一名音频导演节点。
目标：输出真实可用的音频导演说明，而不是音频链接。

{_render_context(task_input, upstream)}

输出要求：
1. 只输出中文。
2. 只输出 <WORKFLOW_JSON> 和 </WORKFLOW_JSON> 包裹的 JSON。
3. 不要输出 markdown，不要解释，不要寒暄。
4. JSON 必须包含：
versionTitle, performanceDirection, instrumentation, chorusLift, introDirection, endingDirection, productionNotes, renderPrompt
5. versionTitle、performanceDirection、chorusLift、introDirection、endingDirection、renderPrompt 都必须是字符串。
6. instrumentation 与 productionNotes 都必须是字符串数组，不能返回对象或单个字符串。
7. 不要返回 audioUrl。
"""


def _dig_value(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ProviderError(f"响应里找不到文本字段路径: {path}")
        current = current[part]
    return current


def _extract_text_from_response(payload: Any) -> str:
    configured_path = os.environ.get(TEXT_API_RESPONSE_TEXT_PATH_ENV)
    if configured_path:
        value = _dig_value(payload, configured_path)
        if not isinstance(value, str) or not value.strip():
            raise ProviderError(f"响应字段 {configured_path} 不是有效文本")
        return value

    candidates = [
        "text",
        "output_text",
        "content",
        "message",
    ]
    if isinstance(payload, dict):
        for key in candidates:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                text = first_choice.get("text")
                if isinstance(text, str) and text.strip():
                    return text
                message = first_choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                text = item.get("text")
                                if isinstance(text, str) and text.strip():
                                    return text
        output = payload.get("output")
        if isinstance(output, list) and output:
            for item in output:
                if isinstance(item, dict):
                    content = item.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict):
                                text = block.get("text")
                                if isinstance(text, str) and text.strip():
                                    return text
        if isinstance(payload.get("data"), dict):
            return _extract_text_from_response(payload["data"])

    raise ProviderError(
        "文本接口响应里没有可识别的文本字段。可设置 GSTACK_TEXT_API_RESPONSE_TEXT_PATH 指定路径。"
    )


def _build_request_payload(stage: str, prompt: str) -> dict[str, Any]:
    request_format = os.environ.get(TEXT_API_REQUEST_FORMAT_ENV, "prompt").strip().lower() or "prompt"
    model = os.environ.get(TEXT_API_MODEL_ENV)

    if request_format == "chat_completions":
        payload: dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        }
        if model:
            payload["model"] = model
        return payload

    prompt_field = os.environ.get(TEXT_API_PROMPT_FIELD_ENV, "prompt").strip() or "prompt"
    payload = {prompt_field: prompt, "stage": stage}
    if model:
        payload["model"] = model
    return payload


def call_stage_text(stage: str, prompt: str) -> str:
    url = os.environ.get(TEXT_API_URL_ENV)
    if not url:
        raise ProviderError(
            "未配置文本接口。请设置 GSTACK_TEXT_API_URL，并确保 worker 进程继承到该环境变量。"
        )
    payload = _build_request_payload(stage, prompt)

    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get(TEXT_API_KEY_ENV)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    timeout_seconds = float(os.environ.get(TEXT_API_TIMEOUT_ENV, "60"))
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            logger.info("stage=%s text_api_request url=%s timeout=%s", stage, url, timeout_seconds)
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ProviderError(f"文本接口请求失败: {exc}") from exc

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise ProviderError("文本接口返回的不是 JSON") from exc

    logger.info("stage=%s text_api_response status=%s", stage, response.status_code)
    return _extract_text_from_response(response_payload)
