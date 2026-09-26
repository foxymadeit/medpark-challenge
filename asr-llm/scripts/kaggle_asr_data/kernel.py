"""Kaggle entry: install what build.py needs, fetch it from the branch, run it."""

import subprocess
import sys

REPO = "/kaggle/working/repo"


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


sh(f"git clone -q --depth 1 -b samoilov-asr-llm https://github.com/foxymadeit/medpark-challenge {REPO}")
sh("pip install -q uroman huggingface_hub soundfile pyarrow librosa")
sh(f"{sys.executable} {REPO}/asr-llm/scripts/kaggle_asr_data/build.py")
sh(f"rm -rf {REPO}")  # keep the output folder to the dataset only
