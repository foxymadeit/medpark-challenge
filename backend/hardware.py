"""Model sizes for the machine Liminal runs on, so one install works on the
reference GPU server (one 16 GB card), a CPU-only server with 32 GB of RAM,
and a demo laptop. LIMINAL_PROFILE names a profile outright, and any MOM_*
setting already in the environment wins over the profile's."""

import os
import shutil
import subprocess

PROFILES = {
    "gpu": {"MOM_DEVICE": "cuda", "MOM_ASR_COMPUTE_TYPE": "int8_float16", "MOM_ASR_MODEL_DIR": "models/whisper",
            "MOM_LLM_MODEL": "qwen3:8b"},
    "cpu": {"MOM_DEVICE": "cpu", "MOM_ASR_COMPUTE_TYPE": "int8", "MOM_ASR_MODEL_DIR": "models/whisper-turbo",
            "MOM_LLM_MODEL": "qwen3:8b"},
    "laptop": {"MOM_DEVICE": "cpu", "MOM_ASR_COMPUTE_TYPE": "int8", "MOM_ASR_MODEL_DIR": "models/whisper-turbo",
               "MOM_LLM_MODEL": "qwen3:4b"},
}
GPU_GB, CPU_RAM_GB = 15, 30   # a "16 GB" card reports a little under 16


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


def detect(gpu_gb: float | None = None, ram_gb: float | None = None) -> str:
    gpu_gb = gpu_memory_gb() if gpu_gb is None else gpu_gb
    if gpu_gb >= GPU_GB:
        return "gpu"
    return "cpu" if (globals()["ram_gb"]() if ram_gb is None else ram_gb) >= CPU_RAM_GB else "laptop"


def profile() -> str:
    named = os.getenv("LIMINAL_PROFILE", "")
    return named if named in PROFILES else detect()


def stage_env(name: str | None = None) -> dict:
    """The profile's settings that the environment does not already set."""
    return {k: v for k, v in PROFILES[name or profile()].items() if k not in os.environ}
