"""Kaggle Notebook: NVIDIA Canary-1B-v2 on the same Medpark audio as Whisper v2.

Paste this file into one notebook cell, or run it as a script on Kaggle.
Accelerator: GPU T4. Internet ON (this cell downloads the weights).
Attach the organizers' audio as a private Dataset. Do not upload real patient audio.

Canary transcribes only when you name a source language. This meeting is
mixed Romanian / Russian / English, so the pass uses Romanian (source=ro,
target=ro = transcribe, not translate). Russian and English stretches can
come out worse than Whisper large-v3 — that difference is the point of the run.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

AUDIO_ROOT = Path("/kaggle/input")
WAV = Path("/kaggle/working/audio_16k.wav")
OUT = Path("/kaggle/working/transcript_canary.json")
SOURCE_LANG = "ro"
TARGET_LANG = "ro"


def find_audio(root: Path) -> Path:
    hits = list(root.rglob("*.m4a")) + list(root.rglob("*.wav")) + list(root.rglob("*.mp3"))
    if not hits:
        raise FileNotFoundError(f"No audio under {root}. Add a Dataset and fix AUDIO_ROOT.")
    return hits[0]


def to_wav(src: Path, dest: Path) -> None:
    subprocess.check_call(
        ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dest)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def transcribe(wav: Path) -> dict:
    from nemo.collections.asr.models import ASRModel

    t0 = time.perf_counter()
    model = ASRModel.from_pretrained(model_name="nvidia/canary-1b-v2")
    load_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    output = model.transcribe(
        [str(wav)],
        source_lang=SOURCE_LANG,
        target_lang=TARGET_LANG,
        timestamps=True,
    )
    asr_s = time.perf_counter() - t1
    hyp = output[0]
    stamps = (getattr(hyp, "timestamp", None) or {}).get("segment") or []
    rows = []
    for stamp in stamps:
        text = (stamp.get("segment") or stamp.get("text") or "").strip()
        if not text:
            continue
        rows.append({"start": float(stamp["start"]), "end": float(stamp["end"]), "text": text})
    if not rows:
        text = (getattr(hyp, "text", None) or str(hyp)).strip()
        rows = [{"start": 0.0, "end": 0.0, "text": text}] if text else []
    duration = max((r["end"] for r in rows), default=0.0)
    return {
        "file": str(wav),
        "engine": "nvidia/canary-1b-v2",
        "source_lang": SOURCE_LANG,
        "target_lang": TARGET_LANG,
        "audio_s": round(duration, 1),
        "load_s": round(load_s, 1),
        "asr_s": round(asr_s, 1),
        "realtime_factor": round((duration / asr_s) if asr_s else 0.0, 1),
        "segments": rows,
        "text": "\n".join(f"[{r['start']:.1f}-{r['end']:.1f}] {r['text']}" for r in rows),
    }


def main() -> None:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", "nemo_toolkit[asr]"],
    )
    audio = find_audio(AUDIO_ROOT)
    print(f"audio: {audio}")
    to_wav(audio, WAV)
    result = transcribe(WAV)
    print(
        f"lang={result['source_lang']}  audio={result['audio_s']}s  "
        f"load={result['load_s']}s  asr={result['asr_s']}s  "
        f"RTFx={result['realtime_factor']}\n"
    )
    print(result["text"][:4000])
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT)


main()
