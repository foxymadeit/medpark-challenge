from __future__ import annotations

import time
from pathlib import Path

from .asr import WhisperAsr, transcribe_batches
from .audio import decode_audio, duration_s
from .batching import pack_batches
from .config import settings
from .llm import LocalLlm
from .schemas import Minutes, PipelineResult, SpeechSegment, Transcript
from .vad import energy_vad


def transcribe_audio(audio_path: Path) -> tuple[Transcript, dict[str, float]]:
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

    engine = WhisperAsr()
    t0 = time.perf_counter()
    chunks = transcribe_batches(engine, batches)
    timings["asr"] = time.perf_counter() - t0
    engine.close()

    segments = [
        SpeechSegment(start=c.start, end=c.end, text=c.text, language=c.language)
        for c in chunks
        if c.text
    ]
    transcript = Transcript(
        source=str(audio_path),
        duration_s=duration_s(audio),
        asr_device=engine.device,
        asr_model=engine.model_id,
        segments=segments,
        text=_format_transcript(segments),
    )
    return transcript, timings


def write_minutes(transcript: Transcript, meeting_type: str) -> tuple[Minutes, float]:
    t0 = time.perf_counter()
    minutes = LocalLlm().extract_minutes(transcript, meeting_type)
    return minutes, time.perf_counter() - t0


def run_pipeline(
    audio_path: Path,
    meeting_type: str = "administrative",
    skip_llm: bool = False,
) -> PipelineResult:
    transcript, timings = transcribe_audio(audio_path)
    if skip_llm:
        minutes = Minutes(title=audio_path.stem, meeting_type=meeting_type, summary="")  # type: ignore[arg-type]
        timings["llm"] = 0.0
        return PipelineResult(transcript=transcript, minutes=minutes, elapsed_s=timings)

    minutes, llm_s = write_minutes(transcript, meeting_type)
    timings["llm"] = llm_s
    return PipelineResult(transcript=transcript, minutes=minutes, elapsed_s=timings)


def _format_transcript(segments: list[SpeechSegment]) -> str:
    lines = []
    for seg in segments:
        lang = f" ({seg.language})" if seg.language else ""
        lines.append(f"[{seg.start:.1f}-{seg.end:.1f}]{lang} {seg.text}")
    return "\n".join(lines)
