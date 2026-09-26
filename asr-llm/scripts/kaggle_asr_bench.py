"""Kaggle Notebook bench: faster-whisper on a 16 GB NVIDIA GPU.

This is a *development* speed/quality check. The demo still runs on-prem.
Do not upload real hospital recordings — only the organizers' anonymized files.

Setup in Kaggle:
1. New Notebook → Accelerator: GPU T4 (16 GB).
2. Add the Medpark audio as a private Dataset.
3. Run the cells once with Internet ON (model download).
4. Optionally turn Internet OFF and run again from the local cache.
"""

from __future__ import annotations

import time
from pathlib import Path

# --- cell 1: install ---
# %pip install -q faster-whisper

from faster_whisper import WhisperModel

AUDIO = Path("/kaggle/input")  # point this at the uploaded m4a after listing
MODEL_DIR = Path("/kaggle/working/whisper-large-v3")
OUT = Path("/kaggle/working/transcript.json")


def find_audio(root: Path) -> Path:
    hits = list(root.rglob("*.m4a")) + list(root.rglob("*.wav")) + list(root.rglob("*.mp3"))
    if not hits:
        raise FileNotFoundError(f"No audio under {root}. Add a Dataset and fix AUDIO.")
    return hits[0]


def transcribe(path: Path) -> dict:
    t0 = time.perf_counter()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(
        "large-v3",
        device="cuda",
        compute_type="float16",
        download_root=str(MODEL_DIR),
    )
    load_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    segments, info = model.transcribe(
        str(path),
        language=None,
        multilingual=True,
        task="transcribe",
        beam_size=5,
        condition_on_previous_text=False,
        vad_filter=True,
    )
    rows = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
    asr_s = time.perf_counter() - t1
    duration = max((r["end"] for r in rows), default=0.0)
    rtf = (duration / asr_s) if asr_s else 0.0
    return {
        "file": str(path),
        "language": getattr(info, "language", None),
        "audio_s": round(duration, 1),
        "load_s": round(load_s, 1),
        "asr_s": round(asr_s, 1),
        "realtime_factor": round(rtf, 1),
        "text": "\n".join(f"[{r['start']:.1f}-{r['end']:.1f}] {r['text']}" for r in rows if r["text"]),
    }


if __name__ == "__main__":
    audio = find_audio(AUDIO)
    result = transcribe(audio)
    print(
        f"{result['file']}\n"
        f"lang={result['language']}  audio={result['audio_s']}s  "
        f"load={result['load_s']}s  asr={result['asr_s']}s  "
        f"RTFx={result['realtime_factor']}\n"
    )
    print(result["text"][:4000])
    OUT.write_text(__import__("json").dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
