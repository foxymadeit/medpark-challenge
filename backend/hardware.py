"""Model sizes for the machine Liminal runs on, so one install works on the
reference GPU server (one 16 GB card), a CPU-only server with 32 GB of RAM,
and a demo laptop. LIMINAL_PROFILE names a profile outright, and any MOM_*
setting already in the environment wins over the profile's."""

import os
import platform
import shutil
import subprocess
import sys

PROFILES = {
    # Measured on one T4 (27 Sep): batched greedy transcription, 9.1 min for an hour; gpt-oss:20b
    # writes an hour's minutes where qwen3:8b ran out of tokens (minutes rounds 3 and 4).
    # MOM_PARALLEL 1: gpt-oss:20b fills most of a 16 GB card, so one request at a time is fastest.
    "gpu": {"MOM_DEVICE": "cuda", "MOM_ASR_COMPUTE_TYPE": "int8_float16", "MOM_ASR_MODEL_DIR": "models/whisper",
            "MOM_LLM_MODEL": "gpt-oss:20b", "MOM_ASR_BATCH_SIZE": "8", "MOM_ASR_BEAM_SIZE": "1",
            "MOM_ASR_RETRY": "loops", "MOM_ASR_ADAPTIVE_LANGUAGES": "true", "MOM_PARALLEL": "1"},
    # Batched decoding pays off on a GPU; on a CPU one utterance at a time is as fast.
    "cpu": {"MOM_DEVICE": "cpu", "MOM_ASR_COMPUTE_TYPE": "int8", "MOM_ASR_MODEL_DIR": "models/whisper-turbo",
            "MOM_LLM_MODEL": "gpt-oss:20b", "MOM_ASR_BATCH_SIZE": "1"},
    "laptop": {"MOM_DEVICE": "cpu", "MOM_ASR_COMPUTE_TYPE": "int8", "MOM_ASR_MODEL_DIR": "models/whisper-turbo",
               "MOM_LLM_MODEL": "qwen3:4b", "MOM_ASR_BATCH_SIZE": "1"},
    # Apple Silicon: faster-whisper has no Apple-GPU backend, so large-v3 runs through MLX on the GPU
    # (asr_llm/mlx_asr.py); Ollama uses the same GPU for gpt-oss:20b, which needs ~13 GB of the shared memory.
    "mac": {"MOM_ASR_ENGINE": "mlx", "MOM_LLM_MODEL": "gpt-oss:20b", "MOM_ASR_BATCH_SIZE": "1"},
}
GPU_GB, CPU_RAM_GB, MAC_RAM_GB = 15, 30, 20   # a "16 GB" card reports a little under 16


def gpu_memory_gb() -> float:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return 0.0
    try:
        out = subprocess.run([exe, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        return max((int(x) / 1024 for x in out.split() if x.isdigit()), default=0.0)
    except (OSError, subprocess.SubprocessError):
        return 0.0


def ram_gb() -> float:
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3


def apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def detect(gpu_gb: float | None = None, ram_gb: float | None = None, apple: bool | None = None) -> str:
    gpu_gb = gpu_memory_gb() if gpu_gb is None else gpu_gb
    if gpu_gb >= GPU_GB:
        return "gpu"
    ram = globals()["ram_gb"]() if ram_gb is None else ram_gb
    if (apple_silicon() if apple is None else apple) and ram >= MAC_RAM_GB:
        return "mac"
    return "cpu" if ram >= CPU_RAM_GB else "laptop"


def profile() -> str:
    named = os.getenv("LIMINAL_PROFILE", "")
    return named if named in PROFILES else detect()


def stage_env(name: str | None = None) -> dict:
    """The profile's settings that the environment does not already set."""
    return {k: v for k, v in PROFILES[name or profile()].items() if k not in os.environ}
