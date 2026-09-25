from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MeetingType = Literal["medical", "executive", "administrative"]


class SpeechSegment(BaseModel):
    start: float
    end: float
    text: str
    language: str | None = None
    speaker: str | None = None


class Transcript(BaseModel):
    source: str
    duration_s: float
    asr_backend: str
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
