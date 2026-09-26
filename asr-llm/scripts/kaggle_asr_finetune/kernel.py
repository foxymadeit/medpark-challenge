"""Kaggle entry for asr_train.finetune: fetch the branch, install NeMo, train on both T4s.

Input: the output of the medpark-asr-data kernel (kernel_sources). If a previous run of this
kernel left a checkpoint, attach its output too: the newest ft/ckpt/{final,last}.ckpt found
is resumed. Locally, run `python -m asr_train.finetune` from asr-llm/ instead.
"""

import subprocess
import sys
from pathlib import Path

BRANCH = "samoilov-asr-llm"
REPO = "/tmp/repo"


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


sh(f"git clone -q --depth 1 -b {BRANCH} https://github.com/foxymadeit/medpark-challenge {REPO}")
sh("pip install -q 'nemo_toolkit[asr]'")
inputs = Path("/kaggle/input")
data = next(inputs.rglob("asrdata/train.jsonl")).parent
# final.ckpt is written after fit returns, last.ckpt at every dev check: prefer final when both exist.
resume = next(inputs.rglob("ft/ckpt/final.ckpt"), None) or next(inputs.rglob("ft/ckpt/last.ckpt"), None)
cmd = [sys.executable, "-m", "asr_train.finetune", "--data-dir", str(data), "--out", "/kaggle/working/ft", "--max-hours", "11"]
if resume:
    cmd += ["--resume", str(resume)]
print("+", " ".join(cmd), flush=True)
subprocess.run(cmd, check=True, cwd=f"{REPO}/asr-llm")
