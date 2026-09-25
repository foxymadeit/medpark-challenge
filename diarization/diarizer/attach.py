"""Put names on a Whisper transcript: each line goes to the speaker whose
turns overlap it most. With word timestamps, a line that two people share is
split where the voice changes, so an action item lands on whoever said it.

Turns and transcript must share a time base (seconds from the start of the
same recording), which holds for `diarizer file` and Whisper run on that file.
"""


def load_segments(obj) -> list[dict]:
    """openai-whisper JSON, a bare list (faster-whisper dumps), or whisper.cpp -oj."""
    if isinstance(obj, dict) and "transcription" in obj:
        return [{"start": s["offsets"]["from"] / 1000, "end": s["offsets"]["to"] / 1000, "text": s["text"]}
                for s in obj["transcription"]]
    segs = obj["segments"] if isinstance(obj, dict) and "segments" in obj else obj
    if not isinstance(segs, list):
        raise ValueError("unrecognised transcript: expected 'segments', 'transcription' or a list of segments")
    out = []
    for s in segs:
        seg = {"start": float(s["start"]), "end": float(s["end"]), "text": s["text"]}
        if s.get("words"):
            seg["words"] = s["words"]
        out.append(seg)
    return out


def _speaker(a: float, b: float, turns, max_gap: float):
    # ponytail: linear scan per word, about 10M steps for an hour; bisect on sorted starts if it ever shows up
    overlap, nearest, gap = {}, None, max_gap
    for t in turns:
        ov = min(b, t["end"]) - max(a, t["start"])
        if ov > 0:
            overlap[t["speaker"]] = overlap.get(t["speaker"], 0.0) + ov
        elif -ov <= gap:
            nearest, gap = t["speaker"], -ov
    return max(overlap, key=overlap.get) if overlap else nearest


def attach(segments, turns, max_gap: float = 2.0) -> list[dict]:
    """[{speaker, start, end, text}] in transcript order. speaker is None when
    no turn is within max_gap seconds (usually noise Whisper wrote down)."""
    out = []
    for s in segments:
        if not s.get("words"):
            out.append({"speaker": _speaker(s["start"], s["end"], turns, max_gap),
                        "start": s["start"], "end": s["end"], "text": s["text"].strip()})
            continue
        runs = []
        for w in s["words"]:
            spk = _speaker(w["start"], w["end"], turns, max_gap)
            if runs and runs[-1]["speaker"] == spk:
                runs[-1] = {**runs[-1], "end": w["end"], "text": runs[-1]["text"] + w["word"]}
            else:
                runs.append({"speaker": spk, "start": w["start"], "end": w["end"], "text": w["word"]})
        out += [{**r, "text": r["text"].strip()} for r in runs]
    return out
