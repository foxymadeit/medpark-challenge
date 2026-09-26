from __future__ import annotations

import json
import re
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


# "12. [R] (ru) text": a numbered line of a data/recording_scripts/*.md script.
_SCRIPT_LINE = re.compile(r"^\s*\d+\.\s*\[[^\]]+\]\s*\([^)]*\)\s*(.*)$")
_STAGE = re.compile(r"\*\([^)]*\)\*")  # "*(answers the phone)*": a direction, not speech


def script_text(path: Path) -> str:
    """The spoken lines of a recording script, without speaker/language tags, directions and overlap marks."""
    spoken = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if m := _SCRIPT_LINE.match(line):
            spoken.append(re.sub(r"\s+", " ", _STAGE.sub(" ", m.group(1)).replace("⟂", " ")).strip())
    return " ".join(spoken)


def gold_text(path: Path = GOLD) -> str:
    """A reference as one string. A gold .txt drops "#" lines (notes and timestamps); a recording script .md keeps its spoken lines."""
    if path.suffix == ".md":
        return script_text(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    return " ".join(line for line in lines if line.strip() and not line.lstrip().startswith("#"))
