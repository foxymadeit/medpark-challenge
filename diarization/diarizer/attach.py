"""Put names on a Whisper transcript: each line goes to the speaker whose
turns overlap it most. With word timestamps, a line that two people share is
split where the voice changes, so an action item lands on whoever said it.

Turns and transcript must share a time base (seconds from the start of the
same recording), which holds for `diarizer file` and Whisper run on that file.
"""

import bisect


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


class _Turns:
    """Turns sorted by start, so each lookup visits only the turns that can
    touch the interval: O(log T + hits) instead of a scan of every turn."""

    def __init__(self, turns):
        self.t = sorted(turns, key=lambda t: t["start"])
        self.starts = [t["start"] for t in self.t]
        self.longest = max((t["end"] - t["start"] for t in self.t), default=0.0)

    def speaker(self, a: float, b: float, max_gap: float):
        overlap, nearest, gap = {}, None, max_gap
        i = bisect.bisect_left(self.starts, b + max_gap)
        while i > 0 and self.starts[i - 1] >= a - max_gap - self.longest:
            i -= 1
            t = self.t[i]
            ov = min(b, t["end"]) - max(a, t["start"])
            if ov > 0:
                overlap[t["speaker"]] = overlap.get(t["speaker"], 0.0) + ov
            elif -ov <= gap:
                nearest, gap = t["speaker"], -ov
        return max(overlap, key=overlap.get) if overlap else nearest


def attach(segments, turns, max_gap: float = 2.0) -> list[dict]:
    """[{speaker, start, end, text}] in transcript order. speaker is None when
    no turn is within max_gap seconds (usually noise Whisper wrote down)."""
    index, out = _Turns(turns), []
    for s in segments:
        if not s.get("words"):
            out.append({"speaker": index.speaker(s["start"], s["end"], max_gap),
                        "start": s["start"], "end": s["end"], "text": s["text"].strip()})
            continue
        runs = []
        for w in s["words"]:
            spk = index.speaker(w["start"], w["end"], max_gap)
            if runs and runs[-1]["speaker"] == spk:
                runs[-1] = {**runs[-1], "end": w["end"], "text": runs[-1]["text"] + w["word"]}
            else:
                runs.append({"speaker": spk, "start": w["start"], "end": w["end"], "text": w["word"]})
        out += [{**r, "text": r["text"].strip()} for r in runs]
    return out
