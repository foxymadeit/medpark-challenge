from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

ASR_ROOT = Path(__file__).resolve().parents[1]  # asr-llm/
GOLD = ASR_ROOT / "data" / "gold_0-181s.txt"


def sh(cmd: list[str] | str, **kwargs) -> None:
    print("+", cmd if isinstance(cmd, str) else shlex.join(map(str, cmd)), flush=True)
    subprocess.run(cmd, shell=isinstance(cmd, str), check=True, **kwargs)


def ffmpeg_16k(src: Path | str, dest: Path, *extra: str) -> Path:
    """Any audio -> 16 kHz mono WAV. `extra` goes after the input (e.g. "-t", "181")."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    sh(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src), *extra, "-ac", "1", "-ar", "16000", str(dest)])
    return dest


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def gold_text(path: Path = GOLD) -> str:
    """The hand-corrected gold as one string; "#" lines are notes and timestamps, not speech."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return " ".join(line for line in lines if line.strip() and not line.lstrip().startswith("#"))
