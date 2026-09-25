from __future__ import annotations

import json
import time
from pathlib import Path

from .asr import pick_backend, transcribe_batches
from .audio import decode_audio, duration_s
from .batching import assign_speakers, pack_batches
from .config import settings
from .llm import LocalLlm
from .schemas import Minutes, PipelineResult, SpeechSegment, Transcript
from .vad import energy_vad


def run_pipeline(
    audio_path: Path,
    meeting_type: str = "administrative",
    diarization_json: Path | None = None,
    skip_llm: bool = False,
) -> PipelineResult:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    audio = decode_audio(audio_path)
    timings["decode"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    spans = energy_vad(audio)
    if not spans:
        spans = [(0.0, duration_s(audio))]
    batches = pack_batches(audio, spans)
    timings["vad_batch"] = time.perf_counter() - t0

    speakers = [None] * len(batches)
    if diarization_json:
        session = json.loads(diarization_json.read_text(encoding="utf-8"))
        speakers = assign_speakers(batches, session.get("turns", []))

    engine = pick_backend()
    t0 = time.perf_counter()
    chunks = transcribe_batches(engine, batches, settings.sample_rate)
    timings["asr"] = time.perf_counter() - t0

    segments = [
        SpeechSegment(
            start=chunk.start,
            end=chunk.end,
            text=chunk.text,
            language=chunk.language,
            speaker=speakers[i],
        )
        for i, chunk in enumerate(chunks)
        if chunk.text
    ]
    transcript = Transcript(
        source=str(audio_path),
        duration_s=duration_s(audio),
        asr_backend=engine.name,
        asr_model=engine.model_id,
        segments=segments,
        text=_format_transcript(segments),
    )

    if skip_llm:
        minutes = Minutes(
            title=audio_path.stem,
            meeting_type=meeting_type,  # type: ignore[arg-type]
            summary="",
        )
        timings["llm"] = 0.0
        return PipelineResult(transcript=transcript, minutes=minutes, elapsed_s=timings)

    t0 = time.perf_counter()
    minutes = LocalLlm().extract_minutes(transcript, meeting_type)
    timings["llm"] = time.perf_counter() - t0
    return PipelineResult(transcript=transcript, minutes=minutes, elapsed_s=timings)


def _format_transcript(segments: list[SpeechSegment]) -> str:
    lines = []
    for seg in segments:
        stamp = f"[{seg.start:.1f}-{seg.end:.1f}]"
        who = f"{seg.speaker}: " if seg.speaker else ""
        lang = f" ({seg.language})" if seg.language else ""
        lines.append(f"{stamp}{lang} {who}{seg.text}")
    return "\n".join(lines)
