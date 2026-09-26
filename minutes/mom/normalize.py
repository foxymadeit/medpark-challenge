"""Any transcript -> numbered lines (L0001, L0002, ...) that every fact cites.

Reads plain text (with or without [hh:mm:ss] times and "Speaker:" labels),
SRT, WebVTT, openai-whisper and faster-whisper JSON, whisper.cpp -oj JSON,
and the diarizer's attach output. A diarizer session (turns with speaker,
start, end) adds speakers to lines that have none, by the largest overlap.
"""

import json
import re
from pathlib import Path

from .schemas import Line

_TIME = r"(\d{1,2}):(\d{2})(?::(\d{2}))?(?:[.,](\d{1,3}))?"
_CUE = re.compile(rf"{_TIME}\s*-->\s*{_TIME}")
_SPEAKER = re.compile(r"^\s*([A-ZĂÂÎȘȚА-ЯЁ][^:\n]{0,40}?|Speaker \d+|SPEAKER_\d+)\s*:\s+(.+)$")
MAX_BYTES = 20 * 1024 * 1024


def load_transcript(path, session=None) -> list:
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"{path.name} is larger than {MAX_BYTES // 2**20} MB; that is not a meeting transcript")
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    suffix = path.suffix.lower()
    data = _try_json(raw) if suffix == ".json" or raw.lstrip()[:1] in "[{" else None
    if data is not None:
        rows = _json_rows(data)
    elif suffix in (".srt", ".vtt") or _CUE.search(raw[:2000]):
        rows = _cue_rows(raw)
    else:
        rows = _text_rows(raw)
    if session:
        rows = _attach(rows, json.loads(Path(session).read_text(encoding="utf-8")).get("turns") or [])
    lines = []
    for start, end, speaker, text in rows:
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            lines.append(Line(f"L{len(lines) + 1:04d}", float(start or 0.0), float(end or start or 0.0), speaker.strip(), text))
    return lines


def _try_json(raw: str):
    try:
        return json.loads(raw)
    except (ValueError, RecursionError):   # RecursionError: a file of deeply nested brackets
        return None


def _seconds(h, m, s, ms) -> float:
    if s is None:        # mm:ss
        h, m, s = 0, h, m
    return int(h) * 3600 + int(m) * 60 + int(s) + (int(ms.ljust(3, "0")) / 1000 if ms else 0)


def _split_speaker(text: str):
    m = _SPEAKER.match(text)
    return (m.group(1), m.group(2)) if m else ("", text)


def _text_rows(raw: str) -> list:
    rows, stamp = [], re.compile(rf"^\s*\[?{_TIME}\]?\s*")
    for block in re.split(r"\n\s*\n|\n", raw):
        if not block.strip():
            continue
        t = stamp.match(block)
        start = _seconds(*t.groups()) if t else 0.0
        speaker, text = _split_speaker(block[t.end():] if t else block)
        rows.append([start, start, speaker, text])
    for a, b in zip(rows, rows[1:]):   # a line lasts until the next one starts
        if b[0] > a[0]:
            a[1] = b[0]
    return rows


def _cue_rows(raw: str) -> list:
    rows = []
    for block in re.split(r"\n\s*\n", raw.replace("\r", "")):
        m = _CUE.search(block)
        if not m:
            continue
        g = m.groups()
        text = " ".join(l for l in block[m.end():].splitlines() if l.strip())
        v = re.match(r"\s*<v\s+([^>]+)>(.*)", text)
        speaker, text = (v.group(1), re.sub(r"</v>", "", v.group(2))) if v else _split_speaker(text)
        rows.append([_seconds(*g[:4]), _seconds(*g[4:]), speaker, re.sub(r"<[^>]+>", "", text)])
    return rows


def _json_rows(data) -> list:
    if isinstance(data, dict):
        items = data.get("lines") or data.get("segments") or data.get("transcription") or data.get("turns") or []
    else:
        items = data
    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if "offsets" in it:
            start, end = it["offsets"].get("from", 0) / 1000, it["offsets"].get("to", 0) / 1000
        else:
            start, end = it.get("start", 0.0), it.get("end", it.get("start", 0.0))
        speaker = str(it.get("speaker") or it.get("speaker_name") or "")
        speaker, text = (speaker, str(it.get("text", ""))) if speaker else _split_speaker(str(it.get("text", "")))
        rows.append([float(start), float(end), speaker, text])
    return rows


def _attach(rows, turns) -> list:
    for row in rows:
        if row[2]:
            continue
        best, overlap = "", 0.0
        for t in turns:
            o = min(row[1], float(t.get("end", 0))) - max(row[0], float(t.get("start", 0)))
            if o > overlap:
                best, overlap = str(t.get("speaker", "")), o
        row[2] = best
    return rows
