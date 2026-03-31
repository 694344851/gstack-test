from __future__ import annotations

from pathlib import Path
import sys

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.stage_schemas import SourceAnalysisArtifact
from app.text_workflow import StageExecutionFailure, execute_stage_text, extract_marked_json


def test_extract_marked_json_reads_wrapped_object() -> None:
    payload = extract_marked_json(
        """
before
<WORKFLOW_JSON>
{"summary":"摘要"}
</WORKFLOW_JSON>
after
""".strip()
    )

    assert payload == {"summary": "摘要"}


def test_execute_stage_text_retries_and_raises_missing_marker() -> None:
    attempts = 0

    def runner(_: str) -> str:
        nonlocal attempts
        attempts += 1
        return "no markers here"

    with pytest.raises(StageExecutionFailure) as exc_info:
        execute_stage_text(schema=SourceAnalysisArtifact, prompt="prompt", text_runner=runner)

    assert attempts == 3
    assert exc_info.value.failure_kind == "missing_marker"
    assert exc_info.value.attempts == 3


def test_execute_stage_text_retries_and_raises_schema_validation() -> None:
    def runner(_: str) -> str:
        return """
<WORKFLOW_JSON>
{"summary":"摘要"}
</WORKFLOW_JSON>
""".strip()

    with pytest.raises(StageExecutionFailure) as exc_info:
        execute_stage_text(schema=SourceAnalysisArtifact, prompt="prompt", text_runner=runner)

    assert exc_info.value.failure_kind == "schema_validation"
    assert exc_info.value.attempts == 3


def test_execute_stage_text_surfaces_schema_path_for_nested_list_errors() -> None:
    from app.stage_schemas import LyricPlanArtifact

    def runner(_: str) -> str:
        return """
<WORKFLOW_JSON>
{
  "concept": "歌词方向",
  "narrativePOV": "第一人称",
  "sections": [
    {
      "name": "主歌 A",
      "purpose": "铺垫",
      "emotionalBeat": "克制",
      "imagery": "夜路"
    }
  ],
  "hook": "不认命",
  "keyLines": ["句子一", "句子二"],
  "chorusDraft": ["副歌一", "副歌二"],
  "languageStyle": "电影流行",
  "forComposition": "副歌上扬"
}
</WORKFLOW_JSON>
""".strip()

    with pytest.raises(StageExecutionFailure) as exc_info:
        execute_stage_text(schema=LyricPlanArtifact, prompt="prompt", text_runner=runner)

    assert exc_info.value.failure_kind == "schema_validation"
    assert exc_info.value.message == "Schema 校验失败: sections.0.imagery: Input should be a valid list"


def test_execute_stage_text_retries_with_validation_feedback() -> None:
    from app.stage_schemas import LyricPlanArtifact

    prompts: list[str] = []

    def runner(prompt: str) -> str:
        prompts.append(prompt)
        if len(prompts) == 1:
            return """
<WORKFLOW_JSON>
{
  "concept": "歌词方向",
  "narrativePOV": "第一人称",
  "sections": [
    {
      "name": "主歌 A",
      "purpose": "铺垫",
      "emotionalBeat": "克制",
      "imagery": "夜路"
    }
  ],
  "hook": "不认命",
  "keyLines": ["句子一", "句子二"],
  "chorusDraft": ["副歌一", "副歌二"],
  "languageStyle": "电影流行",
  "forComposition": "副歌上扬"
}
</WORKFLOW_JSON>
""".strip()
        return """
<WORKFLOW_JSON>
{
  "concept": "歌词方向",
  "narrativePOV": "第一人称",
  "sections": [
    {
      "name": "主歌 A",
      "purpose": "铺垫",
      "emotionalBeat": "克制",
      "imagery": ["夜路"]
    }
  ],
  "hook": "不认命",
  "keyLines": ["句子一", "句子二"],
  "chorusDraft": ["副歌一", "副歌二"],
  "languageStyle": "电影流行",
  "forComposition": "副歌上扬"
}
</WORKFLOW_JSON>
""".strip()

    artifact = execute_stage_text(schema=LyricPlanArtifact, prompt="prompt", text_runner=runner)

    assert artifact["sections"][0]["imagery"] == ["夜路"]
    assert len(prompts) == 2
    assert "sections.0.imagery: Input should be a valid list" in prompts[1]


def test_execute_stage_text_returns_validated_artifact() -> None:
    def runner(_: str) -> str:
        return """
<WORKFLOW_JSON>
{
  "summary": "摘要",
  "coreConflict": "冲突",
  "themes": ["反抗"],
  "emotionArc": ["压抑"],
  "motifs": ["火光"],
  "audienceLens": "流行听众",
  "lyricFocus": "副歌聚焦宣告"
}
</WORKFLOW_JSON>
""".strip()

    artifact = execute_stage_text(schema=SourceAnalysisArtifact, prompt="prompt", text_runner=runner)

    assert artifact["summary"] == "摘要"
    assert artifact["themes"] == ["反抗"]
