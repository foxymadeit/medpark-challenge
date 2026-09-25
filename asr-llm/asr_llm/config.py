from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
ASR_ROOT = PACKAGE_DIR.parent


class Settings(BaseSettings):
    """Defaults match the brief: 1×16 GB GPU, or CPU with 32 GB RAM."""

    model_config = SettingsConfigDict(env_prefix="MOM_", extra="ignore")

    sample_rate: int = 16_000
    max_batch_s: float = 30.0
    merge_gap_s: float = 0.4
    min_speech_s: float = 0.25
    vad_frame_ms: int = 30
    vad_pad_s: float = 0.2

    device: str = "auto"  # auto | cuda | cpu
    asr_compute_type: str = "int8"
    asr_model_dir: Path = ASR_ROOT / "models" / "whisper"

    llm_gguf: Path = ASR_ROOT / "models" / "llm" / "qwen2.5-7b-instruct-q4_k_m.gguf"
    llm_language: str = "ro"
    llm_ctx: int = 4096

    ffmpeg_bin: str = "ffmpeg"


settings = Settings()
