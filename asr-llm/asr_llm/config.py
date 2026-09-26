from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
ASR_ROOT = PACKAGE_DIR.parent


class Settings(BaseSettings):
    """Defaults match the brief: 1×16 GB GPU, or CPU with 32 GB RAM."""

    model_config = SettingsConfigDict(env_prefix="MOM_", extra="ignore")

    sample_rate: int = 16_000
    max_batch_s: float = 15.0
    # Do not glue utterances across pauses: a pause is where language switches.
    merge_gap_s: float = 0.0
    min_speech_s: float = 0.25
    vad_threshold: float = 0.5
    vad_min_silence_ms: int = 300
    vad_pad_s: float = 0.2

    device: str = "auto"  # auto | cuda | cpu
    asr_compute_type: str = "int8"
    # faster-whisper defaults to 4 threads; the CPU-only profile needs all cores.
    cpu_threads: int = os.cpu_count() or 4
    asr_model_dir: Path = ASR_ROOT / "models" / "whisper"
    # Whisper picks from 99 languages; Moldovan Romanian often wins as ru/lt.
    asr_languages: tuple[str, ...] = ("ro", "ru", "en")
    # Decode in both top languages when their probabilities are this close. 1.0 = always.
    lid_margin: float = 0.25
    # Shorter clips ("Da", "Ага") carry the previous language; LID is noise there.
    min_lid_s: float = 1.5

    llm_gguf: Path = ASR_ROOT / "models" / "llm" / "qwen2.5-7b-instruct-q4_k_m.gguf"
    llm_language: str = "ro"
    # 12 min of mixed RO/RU/EN plus the glossary does not fit in 4096.
    llm_ctx: int = 8192
    glossary_k: int = 24
    # One LLM pass per window; 10 min of RO/RU text + glossary fits llm_ctx.
    llm_window_s: float = 600.0

    ffmpeg_bin: str = "ffmpeg"


settings = Settings()
