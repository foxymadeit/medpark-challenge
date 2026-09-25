from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MOM_", extra="ignore")

    sample_rate: int = 16_000
    max_batch_s: float = 30.0
    merge_gap_s: float = 0.4
    min_speech_s: float = 0.25
    vad_frame_ms: int = 30
    vad_pad_s: float = 0.2

    asr_backend: str = "auto"  # auto | mlx | faster-whisper
    asr_model: str = "large-v3-turbo"
    asr_compute_type: str = "int8"

    ollama_host: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen2.5:14b"
    llm_language: str = "ro"

    glossary_path: Path = REPO_ROOT / "harvard_medical_dictionary.json"
    ffmpeg_bin: str = "ffmpeg"


settings = Settings()
