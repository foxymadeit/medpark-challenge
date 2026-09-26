"""Kaggle entry for the fine-tune: install NeMo, fetch train.py from the branch, run it on both T4s.

Input: the output of the medpark-asr-data kernel (kernel_sources). If a previous run of this
kernel left a checkpoint, attach its output too and set RESUME to .../ft/ckpt/last.ckpt.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO = "/kaggle/working/repo"


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


sh(f"git clone -q --depth 1 -b samoilov-asr-llm https://github.com/foxymadeit/medpark-challenge {REPO}")
sh("pip install -q 'nemo_toolkit[asr]'")
data = next(Path("/kaggle/input").rglob("asrdata/train.jsonl")).parent
last = next(Path("/kaggle/input").rglob("ft/ckpt/last.ckpt"), None)
env = {**os.environ, "DATA_DIR": str(data), "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
if last:
    env["RESUME"] = str(last)
print("data:", data, "resume:", last, flush=True)
subprocess.run([sys.executable, f"{REPO}/asr-llm/scripts/kaggle_asr_finetune/train.py"], check=True, env=env)
sh(f"rm -rf {REPO}")
