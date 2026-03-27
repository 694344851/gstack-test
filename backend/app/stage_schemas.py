from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictStageModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceAnalysisArtifact(StrictStageModel):
    summary: str = Field(min_length=1)
    coreConflict: str = Field(min_length=1)
    themes: list[str] = Field(min_length=1)
    emotionArc: list[str] = Field(min_length=1)
    motifs: list[str] = Field(min_length=1)
    audienceLens: str = Field(min_length=1)
    lyricFocus: str = Field(min_length=1)


class LyricPlanSection(StrictStageModel):
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    emotionalBeat: str = Field(min_length=1)
    imagery: list[str] = Field(min_length=1)


class LyricPlanArtifact(StrictStageModel):
    concept: str = Field(min_length=1)
    narrativePOV: str = Field(min_length=1)
    sections: list[LyricPlanSection] = Field(min_length=1)
    hook: str = Field(min_length=1)
    keyLines: list[str] = Field(min_length=2)
    chorusDraft: list[str] = Field(min_length=2)
    languageStyle: str = Field(min_length=1)
    forComposition: str = Field(min_length=1)


class CompositionSectionDynamic(StrictStageModel):
    section: str = Field(min_length=1)
    dynamic: str = Field(min_length=1)


class CompositionBriefArtifact(StrictStageModel):
    titleProposal: str = Field(min_length=1)
    tempo: str = Field(min_length=1)
    key: str = Field(min_length=1)
    timeSignature: str = Field(min_length=1)
    arrangement: list[str] = Field(min_length=1)
    vocalDirection: str = Field(min_length=1)
    sectionDynamics: list[CompositionSectionDynamic] = Field(min_length=1)
    mixMood: str = Field(min_length=1)


class CoverDirectionArtifact(StrictStageModel):
    coverTitle: str = Field(min_length=1)
    visualConcept: str = Field(min_length=1)
    composition: str = Field(min_length=1)
    palette: list[str] = Field(min_length=1)
    subjectFocus: str = Field(min_length=1)
    negativeSpace: str = Field(min_length=1)
    renderPrompt: str = Field(min_length=1)
    avoid: list[str] = Field(min_length=1)


class AudioRenderArtifact(StrictStageModel):
    versionTitle: str = Field(min_length=1)
    performanceDirection: str = Field(min_length=1)
    instrumentation: list[str] = Field(min_length=1)
    chorusLift: str = Field(min_length=1)
    introDirection: str = Field(min_length=1)
    endingDirection: str = Field(min_length=1)
    productionNotes: list[str] = Field(min_length=1)
    renderPrompt: str = Field(min_length=1)
