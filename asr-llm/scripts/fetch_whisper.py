#!/usr/bin/env python3
"""One-time setup: copy Whisper weights onto disk. Not imported at runtime."""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

MODELS = {
    # Official Systran turbo currently 401 from this network.
    "turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
    "large-v3": "Systran/faster-whisper-large-v3",
}

ROOT = Path(__file__).resolve().parents[1] / "models"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("which", nargs="+", choices=["turbo", "large-v3", "all"])
    args = parser.parse_args()
    names = ["turbo", "large-v3"] if "all" in args.which else args.which
    for name in names:
        dest = ROOT / ("whisper" if name == "large-v3" else "whisper-turbo")
        dest.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {MODELS[name]} -> {dest}")
        snapshot_download(MODELS[name], local_dir=dest)
        print(f"Done: {dest}")


if __name__ == "__main__":
    main()
