from __future__ import annotations

import json
import time
from pathlib import Path

from .asr import WhisperAsr, transcribe_batches
from .audio import decode_audio, duration_s
from .batching import pack_batches
from .clean import collapse_repeat_segments
from .config import settings
from .diarization import load_turns, speaker_for, split_at_turns
from .llm import LocalLlm
from .schemas import Minutes, PipelineResult, SpeechSegment, Transcript, format_segments
from .vad import speech_spans


def transcribe_audio(audio_path: Path, diarization: Path | None = None) -> tuple[Transcript, dict[str, float]]:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    audio = decode_audio(audio_path)
    timings["decode"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    spans = speech_spans(audio)
    if not spans:
        spans = [(0.0, duration_s(audio))]
    turns = load_turns(diarization) if diarization else []
    if turns:
        spans = split_at_turns(spans, turns)
    batches = pack_batches(audio, spans)
    timings["vad_batch"] = time.perf_counter() - t0

    engine = WhisperAsr()
    t0 = time.perf_counter()
    chunks = transcribe_batches(engine, batches)
    timings["asr"] = time.perf_counter() - t0
    engine.close()

    segments = collapse_repeat_segments(
        [
            SpeechSegment(
                start=c.start,
                end=c.end,
                text=c.text,
                language=c.language,
                speaker=speaker_for(c.start, c.end, turns),
            )
            for c in chunks
            if c.text
        ]
    )
    transcript = Transcript(
        source=str(audio_path),
        duration_s=duration_s(audio),
        asr_device=engine.device,
        asr_model=engine.model_id,
        segments=segments,
        text=format_segments(segments),
    )
    return transcript, timings


def write_minutes(
    transcript: Transcript,
    meeting_type: str,
    language: str | None = None,
) -> tuple[Minutes, float]:
    t0 = time.perf_counter()
    minutes = LocalLlm().extract_minutes(transcript, meeting_type, language=language)
    return minutes, time.perf_counter() - t0


def load_transcript(path: Path) -> Transcript:
    """Accept our pipeline JSON or a Kaggle bench file with a `text` field."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "transcript" in raw and isinstance(raw["transcript"], dict):
        return Transcript.model_validate(raw["transcript"])
    text = raw.get("text") or ""
    if not text.strip():
        raise ValueError(f"No transcript text in {path}")
    segments = []
    for row in raw.get("segments") or []:
        if not row.get("text"):
            continue
        segments.append(
            SpeechSegment(
                start=float(row.get("start") or 0),
                end=float(row.get("end") or 0),
                text=str(row["text"]),
                language=row.get("language"),
                speaker=row.get("speaker"),
            )
        )
    segments = collapse_repeat_segments(segments)
    if segments:
        text = format_segments(segments)
    return Transcript(
        source=str(raw.get("file") or path),
        duration_s=float(raw.get("audio_s") or 0),
        asr_device="kaggle",
        asr_model=str(raw.get("engine") or "faster-whisper-large-v3"),
        segments=segments,
        text=text,
    )


def minutes_from_transcript(
    transcript_path: Path,
    meeting_type: str = "medical",
    language: str | None = None,
) -> PipelineResult:
    transcript = load_transcript(transcript_path)
    minutes, llm_s = write_minutes(transcript, meeting_type, language=language)
    return PipelineResult(
        transcript=transcript,
        minutes=minutes,
        elapsed_s={"asr": 0.0, "llm": llm_s},
    )


def run_pipeline(
    audio_path: Path,
    meeting_type: str = "administrative",
    skip_llm: bool = False,
    diarization: Path | None = None,
) -> PipelineResult:
    transcript, timings = transcribe_audio(audio_path, diarization)
    if skip_llm:
        minutes = Minutes(title=audio_path.stem, meeting_type=meeting_type, summary="")  # type: ignore[arg-type]
        timings["llm"] = 0.0
        return PipelineResult(transcript=transcript, minutes=minutes, elapsed_s=timings)

    minutes, llm_s = write_minutes(transcript, meeting_type)
    timings["llm"] = llm_s
    return PipelineResult(transcript=transcript, minutes=minutes, elapsed_s=timings)
