"""Kaggle T4 entry for asr_train.zeroshot: NeMo models first, then the current Whisper pipeline.

Needs the Medpark recording attached as a dataset (any *.m4a under /kaggle/input).
Push from the repo root:  kaggle kernels push -p asr-llm/scripts/kaggle_asr_zeroshot
Locally, run `python -m asr_train.zeroshot` from asr-llm/ instead.
"""

import os
import subprocess
import sys
from pathlib import Path

BRANCH = "samoilov-asr-llm"
REPO = "/tmp/repo"
ASR = f"{REPO}/asr-llm"


def sh(cmd: str, **kwargs) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True, **kwargs)


sh(f"git clone -q --depth 1 -b {BRANCH} https://github.com/foxymadeit/medpark-challenge {REPO}")
sh("pip install -q 'nemo_toolkit[asr]' huggingface_hub soundfile pyarrow")
audio = next(Path("/kaggle/input").rglob("*.m4a"))
bench = f"{sys.executable} -m asr_train.zeroshot --work /kaggle/working"
sh(f"{bench} --audio '{audio}' --models parakeet,canary,jackrabbit", cwd=ASR)
# Whisper runs the asr_llm pipeline: its deps and weights come after the NeMo runs. The test sets are reused.
sh(f"pip install -q -e '{ASR}[asr]' && python scripts/fetch_whisper.py large-v3", cwd=ASR)
env = {**os.environ, "MOM_DEVICE": "cuda", "MOM_ASR_COMPUTE_TYPE": "int8_float16"}
sh(f"{bench} --models whisper", cwd=ASR, env=env)
