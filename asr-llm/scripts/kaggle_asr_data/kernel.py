"""Kaggle entry for asr_train.build_data: fetch the branch, install what it needs, run it.

Kaggle pushes only this file, so the package comes from a clone of BRANCH. Locally,
run `python -m asr_train.build_data` from asr-llm/ instead.
"""

import subprocess

BRANCH = "samoilov-asr-llm"
REPO = "/tmp/repo"  # outside /kaggle/working: the kernel output is the dataset only


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


sh(f"git clone -q --depth 1 -b {BRANCH} https://github.com/foxymadeit/medpark-challenge {REPO}")
sh("pip install -q uroman huggingface_hub soundfile pyarrow librosa")
sh(f"cd {REPO}/asr-llm && python -m asr_train.build_data --out /kaggle/working/asrdata --raw-dir /tmp/raw --prune-raw")
