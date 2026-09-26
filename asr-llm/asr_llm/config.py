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
    # Whisper LID says ru at 0.9 on plain Moldovan Romanian, and forcing ru then
    # *translates*. So these are always decoded; the higher avg_logprob wins.
    asr_always_decode: tuple[str, ...] = ("ro", "ru")
    # The meeting's main language wins close calls by this much avg_logprob.
    home_language: str = "ro"
    home_bias: float = 0.1
    # Shorter clips ("Da", "Ага") carry the previous language; LID is noise there.
    min_lid_s: float = 1.5

    llm_gguf: Path = ASR_ROOT / "models" / "llm" / "qwen2.5-7b-instruct-q4_k_m.gguf"
    # Minutes/fusion model: "" = llm_gguf, a GGUF path, or "ollama:<name>" (e.g. ollama:qwen3.5:9b).
    llm_model: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_timeout_s: float = 600.0
    ollama_think: bool | str = False
    # Models that always reason (gpt-oss cannot turn it off) get a level and extra tokens for it.
    ollama_think_by_prefix: dict[str, str] = {"gpt-oss": "low"}
    ollama_think_budget: int = 1500
    llm_language: str = "ro"
    # 12 min of mixed RO/RU/EN plus the glossary does not fit in 4096.
    llm_ctx: int = 8192
    glossary_k: int = 24
    classify_chars: int = 6000  # transcript sample the type detector sees
    default_meeting_type: str = "administrative"  # only if the user chose none and detection failed
    # One LLM pass per window; 10 min of RO/RU text + glossary fits llm_ctx.
    llm_window_s: float = 600.0

    # Hypothesis fusion: off | single (one LLM looks at the unclear utterances only).
    fusion: str = "off"
    fuse_margin: float = 0.15  # ro/ru scores closer than this = unclear
    fuse_floor: float = -0.8  # best score below this = unclear
    fuse_window: int = 15
    fuse_min_cover: float = 0.85  # share of output words that must come from the hypotheses
    fuse_max_drop: float = 0.05  # may not swap wholesale to a hypothesis scored this much below the best

    # Snap near-miss medical terms to the glossary after ASR (asr_llm/correct.py).
    correct_terms: bool = True
    # Word-level language merge (asr_llm.asr.merge_words): a run of words the other
    # language's decode heard more confidently replaces the winner's words in that time span.
    cs_merge: bool = False
    cs_margin: float = 0.25  # mean word probability the other decode must beat the winner by
    cs_min_words: int = 2
    # Non-empty: one decode prompted with all these language tokens (<|ro|><|ru|>), no per-language decodes.
    asr_joint_languages: tuple[str, ...] = ()

    ffmpeg_bin: str = "ffmpeg"


settings = Settings()
