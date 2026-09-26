"""Kaggle T4 x2: machine-translate the medical dictionary with vLLM (dev time only).

Push from the repo root:  kaggle kernels push -p asr-llm/scripts/kaggle_glossary
Result: /kaggle/working/translated.json -> copy to asr-llm/data/glossary_build/, then run `build_glossary.py merge`.
"""

import shutil
import subprocess

REPO = "/kaggle/working/repo"


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


sh(f"git clone -q --depth 1 -b samoilov-asr-llm https://github.com/foxymadeit/medpark-challenge {REPO}")
# 0.6.x is the last line with dependable T4 (sm75) + AWQ support.
sh("pip install -q vllm==0.6.3.post1")
sh(f"cd {REPO}/asr-llm && python scripts/build_glossary.py translate --model Qwen/Qwen2.5-32B-Instruct-AWQ --tp 2")
shutil.copy(f"{REPO}/asr-llm/data/glossary_build/translated.json", "/kaggle/working/translated.json")
