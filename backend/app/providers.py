from __future__ import annotations

import base64
import io
import math
import struct
import urllib.parse
import wave
from typing import Any


class ProviderError(RuntimeError):
    """Raised when a provider fails in a user-visible way."""


def _safe_title(raw: str) -> str:
    return raw.strip() or "未命名题材"


def source_analysis_provider(task_input: dict[str, Any]) -> dict[str, Any]:
    title = _safe_title(task_input["title"])
    synopsis = task_input.get("synopsis") or f"{title} 的情绪核心被提炼成一首可改编的主题曲。"
    return {
        "summary": synopsis,
        "themes": ["反抗命运", "关系张力", "情绪抬升"],
        "emotionArc": ["压抑", "迟疑", "上扬", "宣告"],
        "motifs": ["夜色", "火光", "轮廓", "余震"],
        "suggestedAudience": "音乐制作爱好者",
    }


def lyric_plan_provider(task_input: dict[str, Any], source_analysis: dict[str, Any]) -> dict[str, Any]:
    title = _safe_title(task_input["title"])
    return {
        "concept": f"围绕《{title}》的情绪主线写一首兼具叙事与副歌爆发力的歌。",
        "sections": [
            {"name": "主歌 A", "purpose": "铺出人物压力与主题"},
            {"name": "预副歌", "purpose": "拉高情绪，准备释放"},
            {"name": "副歌", "purpose": "给出不认命的核心句"},
        ],
        "hook": f"{title} 不只是故事标题，而是副歌里的情绪锚点。",
        "sourceSummary": source_analysis["summary"],
    }


def composition_brief_provider(
    task_input: dict[str, Any],
    lyric_plan: dict[str, Any],
) -> dict[str, Any]:
    title = _safe_title(task_input["title"])
    return {
        "titleProposal": f"{title}·逆光版",
        "bpm": 92,
        "key": "D Minor",
        "timeSignature": "4/4",
        "arrangement": ["低鼓", "弦乐铺底", "合成器氛围", "副歌加厚和声"],
        "vocalDirection": "主歌克制，副歌前推，尾段加叠唱",
        "structure": [section["name"] for section in lyric_plan["sections"]],
    }


def _svg_data_url(title: str) -> str:
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 600 600">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#111923" />
          <stop offset="55%" stop-color="#1E2A39" />
          <stop offset="100%" stop-color="#FFB000" />
        </linearGradient>
      </defs>
      <rect width="600" height="600" fill="url(#g)" />
      <circle cx="460" cy="130" r="80" fill="rgba(60,214,200,0.28)" />
      <text x="60" y="460" fill="#EAF0F8" font-size="44" font-family="sans-serif">{title}</text>
      <text x="60" y="520" fill="#91A1B4" font-size="22" font-family="sans-serif">当前版本 · 电影流行</text>
    </svg>
    """.strip()
    return f"data:image/svg+xml;utf8,{urllib.parse.quote(svg)}"


def cover_direction_provider(
    task_input: dict[str, Any],
    composition_brief: dict[str, Any],
) -> dict[str, Any]:
    title = composition_brief["titleProposal"]
    return {
        "artDirection": "冷色底 + 热色焦点，像深夜配乐控制台里的单曲封面。",
        "coverUrl": _svg_data_url(title),
        "titleLock": title,
    }


def _audio_data_url() -> str:
    sample_rate = 8000
    duration = 0.4
    frequency = 440
    frames = bytearray()
    for index in range(int(sample_rate * duration)):
        value = int(32767 * 0.22 * math.sin(2 * math.pi * frequency * (index / sample_rate)))
        frames.extend(struct.pack("<h", value))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(frames))
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:audio/wav;base64,{encoded}"


def audio_render_provider(
    task_input: dict[str, Any],
    composition_brief: dict[str, Any],
    lyric_plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "title": composition_brief["titleProposal"],
        "audioUrl": _audio_data_url(),
        "durationSeconds": 24,
        "lyricHook": lyric_plan["hook"],
    }

