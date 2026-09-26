#!/usr/bin/env python3
"""One-time setup: copy the Qwen GGUF onto disk. Not imported at runtime."""

from __future__ import annotations

import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

# Official Qwen repo ships this quant as two shards. bartowski republishes
# the same Q4_K_M as one file llama.cpp can open directly.
REPO = "bartowski/Qwen2.5-7B-Instruct-GGUF"
FILENAME = "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
LOCAL_NAME = "qwen2.5-7b-instruct-q4_k_m.gguf"
DEST = Path(__file__).resolve().parents[1] / "models" / "llm"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    target = DEST / LOCAL_NAME
    print(f"Downloading {REPO} {FILENAME} -> {target}")
    path = Path(hf_hub_download(repo_id=REPO, filename=FILENAME, local_dir=DEST))
    if path.resolve() != target.resolve():
        shutil.move(path, target)
    print(f"Done: {target}")


if __name__ == "__main__":
    main()
