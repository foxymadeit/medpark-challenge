from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MeetingType = Literal["medical", "executive", "administrative"]


class Hypothesis(BaseModel):
    language: str
    text: str
    # Whisper: duration-weighted avg_logprob. None for engines that give no score.
    score: float | None = None
    source: str = "whisper"


class SpeechSegment(BaseModel):
    start: float
    end: float
    text: str
    language: str | None = None
    speaker: str | None = None
    # Every decode of this utterance, for the fusion step. `text` is the acoustic winner.
    hypotheses: list[Hypothesis] = Field(default_factory=list)


class Transcript(BaseModel):
    source: str
    duration_s: float
    asr_device: str
    asr_model: str
    segments: list[SpeechSegment]
    text: str


class ActionItem(BaseModel):
    text: str
    owner: str | None = None
    deadline: str | None = None
    source_quote: str | None = None


class Minutes(BaseModel):
    title: str
    meeting_type: MeetingType
    language: str = "ro"
    summary: str
    attendees: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)


class PipelineResult(BaseModel):
    transcript: Transcript
    minutes: Minutes
    elapsed_s: dict[str, float]


def format_segments(segments: list[SpeechSegment]) -> str:
    lines = []
    for seg in segments:
        who = f" {seg.speaker}" if seg.speaker else ""
        lang = f" ({seg.language})" if seg.language else ""
        lines.append(f"[{seg.start:.1f}-{seg.end:.1f}]{who}{lang} {seg.text}")
    return "\n".join(lines)
