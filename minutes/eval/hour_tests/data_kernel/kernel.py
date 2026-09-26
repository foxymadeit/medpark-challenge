"""Kaggle CPU job: build Liminal's one-hour test recordings.

Each source becomes exactly 60:00 of 16 kHz mono FLAC plus whatever reference
it has, under /kaggle/working/hour_tests/<id>/, and one manifest.json lists
them all. A source that fails is recorded in the manifest with its error and
the others carry on. A heartbeat line every minute says where it is.

  rompar_60   Romanian and Moldovan parliamentary speech (HF avramandrei/rompar,
              test split), utterances in record order joined with 0.4 s gaps,
              with the reference transcript and each utterance's times.
  icsi_60     ICSI meeting Bmr005 (English, 71 min, CC BY 4.0), headset mix,
              first 60 min, word reference and speaker turns (RTTM).
  kremlin_60  kremlin.ru meeting with Government members, 23 June 2026
              (Russian, 77 min, medical-staffing topic, CC BY 4.0), first 60
              min, with the official transcript for the chapters that end
              inside the hour.
  md_parl_60  a Moldovan Parliament plenary session (Romanian and Russian), the
              60 min window with the most Russian next to Romanian, picked by
              Whisper-tiny language ID on 30 s windows. No reference: the
              stenograms are not reachable by machine (see manifest note).

All of it is public data; nothing from Medpark goes here.
"""

import html
import io
import json
import os
import re
import shutil
import subprocess
import threading
import time
import traceback
import urllib.request
import zipfile
from pathlib import Path

T0 = time.time()
WORK = Path("/kaggle/working") if Path("/kaggle/working").exists() else Path("/tmp/work")
OUT = WORK / "hour_tests"
TMP = Path("/tmp/hour_src")
HOUR = 3600.0
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Liminal-test-builder"}
STATE = {"source": "", "step": "setup", "done": 0, "total": 4, "since": time.time(), "warnings": []}


def log(msg):
    print(f"[{(time.time() - T0) / 60:6.1f} min] {msg}", flush=True)


def sh(cmd, timeout=3600):
    log(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=True, timeout=timeout)


def heartbeat(every=60, stall=1500):
    while True:
        time.sleep(every)
        quiet = time.time() - STATE["since"]
        problem = f"WARNING: no progress for {quiet / 60:.0f} min" if quiet > stall else "OK"
        if shutil.disk_usage("/tmp").free / 1e9 < 5:
            problem = "WARNING: less than 5 GB free on /tmp"
        log(f"[heartbeat] {100 * STATE['done'] / STATE['total']:.0f}% done | {STATE['source']} {STATE['step']} | {problem}")


def step(name):
    STATE["step"], STATE["since"] = name, time.time()
    log(f"{STATE['source']}: {name}")


def fetch(url, dest, timeout=3600):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        t = time.time()
        while chunk := r.read(1 << 20):
            f.write(chunk)
            STATE["since"] = time.time()
            if time.time() - t > timeout:
                raise TimeoutError(url)
    return dest


def to_hour_flac(src, dest, start=0.0):
    """Exactly 60:00 of 16 kHz mono FLAC from any audio or video file."""
    sh(f"ffmpeg -nostdin -loglevel error -y -ss {start} -i '{src}' -t {HOUR} -vn -ac 1 -ar 16000 -c:a flac '{dest}'")
    dur = float(subprocess.run(f"ffprobe -v error -show_entries format=duration -of csv=p=0 '{dest}'",
                               shell=True, capture_output=True, text=True).stdout.strip() or 0)
    if abs(dur - HOUR) > 1:
        raise ValueError(f"{dest.name} is {dur:.1f} s, not 3600 s")
    return round(dur, 2)


def write_reference(path, header, lines):
    """asr_llm.score's gold format: '#' lines are notes, the rest is the text."""
    path.write_text("\n".join([f"# {h}" for h in header] + lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- sources

def rompar(d):
    import numpy as np
    import pyarrow.parquet as pq
    import soundfile as sf
    from huggingface_hub import hf_hub_download

    step("download test split (430 MB)")
    p = hf_hub_download("avramandrei/rompar", "data/test-00000-of-00001.parquet", repo_type="dataset")
    rows = sorted(pq.read_table(p).to_pylist(), key=lambda r: r["record_id"])
    step("join utterances")
    gap = np.zeros(int(0.4 * 16000), dtype="float32")
    parts, segs, t = [], [], 0.0
    for r in rows:
        audio, sr = sf.read(io.BytesIO(r["audio"]["bytes"]), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(1)
        if sr != 16000:   # the card says 16 kHz; anything else is skipped, not resampled
            continue
        length = len(audio) / sr
        if t + length > HOUR:
            break
        segs.append({"start": round(t, 2), "end": round(t + length, 2), "text": r["transcript"].strip(),
                     "dialect": r.get("dialect"), "record_id": r["record_id"]})
        parts += [audio, gap]
        t += length + len(gap) / sr
    full = np.concatenate(parts)
    full = np.concatenate([full, np.zeros(int(HOUR * 16000) - len(full), dtype="float32")])[: int(HOUR * 16000)]
    sf.write(d / "audio.flac", full, 16000, format="FLAC")
    (d / "segments.json").write_text(json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
    write_reference(d / "reference.txt",
                    [f"ROMPAR test split, {len(segs)} utterances in record order, 0.4 s gaps, 0-{segs[-1]['end']} s",
                     "Utterance times: segments.json"], [s["text"] for s in segs])
    dialects = {}
    for s in segs:
        dialects[s["dialect"]] = dialects.get(s["dialect"], 0) + 1
    return {"languages": ["ro"], "source": "https://huggingface.co/datasets/avramandrei/rompar",
            "license": "not stated on the dataset card; used for internal testing only, not redistributed",
            "reference": "reference.txt", "reference_window_s": segs[-1]["end"], "segments": "segments.json",
            "utterances": len(segs), "dialects": dialects,
            "note": "stitched utterances, not a real meeting: good for speed and Romanian/Moldovan ASR, not for minutes quality"}


def icsi(d):
    import xml.etree.ElementTree as ET

    meeting = "Bmr005"
    step("download headset mix (136 MB)")
    wav = fetch(f"https://groups.inf.ed.ac.uk/ami/ICSIsignals/NXT/{meeting}.interaction.wav", TMP / f"{meeting}.wav")
    step("cut to 60:00")
    to_hour_flac(wav, d / "audio.flac")
    step("annotations")
    z = zipfile.ZipFile(fetch("https://groups.inf.ed.ac.uk/ami/ICSICorpusAnnotations/ICSI_core_NXT.zip", TMP / "icsi_core.zip"))
    words, turns = [], []
    for name in z.namelist():
        base = Path(name).name
        if not base.startswith(meeting + "."):
            continue
        if "/Words/" in name:
            for w in ET.fromstring(z.read(name)).iter("w"):
                s = w.get("starttime")
                if w.get("c") == "W" and s and float(s) < HOUR and w.text:
                    words.append((float(s), w.text.strip()))
        elif "/Segments/" in name:
            for seg in ET.fromstring(z.read(name)).iter("segment"):
                if not seg.get("starttime") or not seg.get("endtime"):
                    continue
                a, b = float(seg.get("starttime")), float(seg.get("endtime"))
                if a < HOUR and b > a:
                    turns.append((seg.get("participant"), a, min(b, HOUR)))
    words.sort()
    turns.sort(key=lambda x: x[1])
    write_reference(d / "reference.txt", [f"ICSI {meeting} word transcript, 0-3600 s, words in time order"],
                    [" ".join(w for _, w in words)])
    (d / "reference.rttm").write_text("".join(f"SPEAKER {meeting} 1 {a:.3f} {b - a:.3f} <NA> <NA> {p} <NA> <NA>\n"
                                              for p, a, b in turns))
    return {"languages": ["en"], "source": f"https://groups.inf.ed.ac.uk/ami/icsi/ (meeting {meeting}, headset mix)",
            "license": "CC BY 4.0 (ICSI Meeting Corpus, Janin et al. 2003)", "reference": "reference.txt",
            "reference_window_s": HOUR, "rttm": "reference.rttm", "words": len(words),
            "speakers": len({p for p, _, _ in turns})}


KREMLIN = "http://kremlin.ru/events/president/news/80090"


def _kremlin_blocks(page):
    """(speaker, text) blocks from the transcript after '* * *'. A minister's
    name comes with a hover card ('Т.Голикова   Голикова Татьяна ... :'),
    Putin's as 'В.Путин:'."""
    tail = page[page.find("<p><b>* * *</b></p>"):]
    blocks, speaker = [], "В.Путин"
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", tail, re.S):
        raw = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).replace("\xa0", " ").strip()
        p = re.sub(r"\s+", " ", raw)
        if p.startswith(("Ссылка на материал", "Текстовая версия")):
            break
        if not p or p == "* * *":
            continue
        # the card's run of spaces is only there before whitespace is collapsed
        card = re.match(r"^([А-ЯЁ]\.[А-ЯЁ][\w-]+) {2,}.*?:\s*(.*)$", raw, re.S) or re.match(r"^([А-ЯЁ]\.[А-ЯЁ][\w-]+):\s*(.*)$", p)
        if card:
            speaker, p = card.group(1), re.sub(r"\s+", " ", card.group(2)).strip()
            blocks.append([speaker, p])
        elif blocks:
            blocks[-1][1] += " " + p
    return blocks


def _anchors(chapters, blocks):
    """(chapter time, index of its first transcript block) for every video
    chapter that names a minister ('А.Никитин о …', 'Комментарий А.Цыденова').
    The chair's chapters name nobody or 'Президента', and he speaks between
    everyone, so only the ministers' chapters pin the text to the clock."""
    out, i = [], 0
    for t, title in chapters:
        # surnames only: titles inflect them (А.Цыденова) and sometimes carry a wrong initial
        names = [n.split(".", 1)[1] for n in re.findall(r"[А-ЯЁ]\.[А-ЯЁ][\w-]+", title) if not n.endswith("Путин")]

        def same(spk):   # Цыбульский ~ Цыбульского, Голикова ~ Голиковой
            s = spk.split(".", 1)[-1]
            return any(len(os.path.commonprefix([s, n])) >= max(4, len(s) - 2) for n in names)
        hit = next((j for j in range(i, len(blocks)) if same(blocks[j][0])), None) if names else None
        if hit is not None:
            out.append((t, hit))
            i = hit + 1
    return out


def kremlin(d):
    step("page")
    page = urllib.request.urlopen(urllib.request.Request(KREMLIN, headers=UA), timeout=60).read().decode("utf-8")
    chapters = [(int(s), html.unescape(t).replace("\xa0", " ")) for s, t in re.findall(
        r'data-value="(\d+)">\s*<span class="mejs-timecode__time">[^<]*</span>\s*<p class="mejs-timecode__title">([^<]*)</p>', page)]
    video = re.search(r"https?://static\.kremlin\.ru/media/events/video/ru/video_low/[\w]+\.mp4", page).group(0)
    blocks = _kremlin_blocks(page)
    # the reference runs up to the last minister's chapter that starts inside the hour
    until_s, until_block = max((a for a in _anchors(chapters, blocks) if a[0] <= HOUR), default=(0, 0))
    if until_block < 3:
        raise ValueError("could not line the transcript up with the video chapters")
    step("download video (400 MB)")
    mp4 = fetch(video, TMP / "kremlin.mp4")
    step("cut to 60:00")
    to_hour_flac(mp4, d / "audio.flac")
    ref = blocks[:until_block]
    write_reference(d / "reference.txt",
                    [f"kremlin.ru official transcript, {KREMLIN}", f"audio 0-{until_s} s ({len(ref)} speaker turns); speaker labels removed",
                     "The official text is lightly edited (fillers and repairs removed), so CER here is a ceiling."],
                    [t for _, t in ref])
    (d / "speakers.json").write_text(json.dumps([{"speaker": s, "text": t} for s, t in ref], ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    (d / "chapters.json").write_text(json.dumps(chapters, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"languages": ["ru"], "source": KREMLIN, "video": video,
            "license": "CC BY 4.0 (kremlin.ru, http://en.kremlin.ru/about/copyrights)",
            "reference": "reference.txt", "reference_window_s": until_s, "chapters": "chapters.json",
            "speakers": sorted({s for s, _ in ref}), "note": "meeting with Government members, 23 June 2026: "
            "mentorship for medical graduates plus current issues, several ministers reporting and the chair giving instructions"}


PARL_PLAYLIST = "https://www.youtube.com/playlist?list=PLAVLfBYYrdyTHyFw9wbJz8jrxR4LGOs1a"
PARL_FALLBACK = ["https://www.youtube.com/watch?v=Fs5pJgXfu84"]   # plenary session, 29 December 2025


def _ytdlp(args):
    for client in ("", "--extractor-args youtube:player_client=tv,web_safari", "--extractor-args youtube:player_client=ios"):
        r = subprocess.run(f"yt-dlp --no-warnings {client} {args}", shell=True, capture_output=True, text=True, timeout=3600)
        if r.returncode == 0:
            return r.stdout
        log(f"yt-dlp {client or 'default'} failed: {r.stderr.strip()[-300:]}")
    raise RuntimeError("yt-dlp could not reach YouTube from Kaggle")


def md_parl(d):
    step("install yt-dlp and faster-whisper")
    sh("pip install -q -U yt-dlp faster-whisper")
    step("pick a long plenary session")
    urls = []
    try:
        entries = json.loads(_ytdlp(f"--flat-playlist -J '{PARL_PLAYLIST}'")).get("entries", [])
        urls = [e["url"] for e in entries[:25] if (e.get("duration") or 0) >= 90 * 60]
    except Exception as e:   # the fallback video still gets its chance
        log(f"playlist failed: {e!r}")
    urls += PARL_FALLBACK
    src, url = None, None
    for url in urls:
        try:
            step(f"download {url}")
            _ytdlp(f"-f bestaudio -o '{TMP}/parl.%(ext)s' '{url}'")
            src = next(TMP.glob("parl.*"))
            break
        except Exception as e:
            log(f"{url}: {e!r}")
    if src is None:
        raise RuntimeError("no plenary session could be downloaded")
    step("language ID every 60 s (Whisper tiny, CPU)")
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio

    audio = decode_audio(str(src), sampling_rate=16000)
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    total = len(audio) / 16000
    lid = []
    for t in range(0, int(total) - 30, 60):
        lang, prob, _ = model.detect_language(audio[t * 16000:(t + 30) * 16000])
        lid.append({"t": t, "lang": lang, "p": round(prob, 2)})
        STATE["since"] = time.time()
    if total < HOUR:
        raise ValueError(f"session is only {total / 60:.0f} min")
    best, start = -1, 0
    for s in range(0, int(total - HOUR) + 1, 300):   # 5-minute steps
        win = [x["lang"] for x in lid if s <= x["t"] < s + HOUR]
        score = min(win.count("ro"), win.count("ru"))
        if score > best:
            best, start = score, s
    step(f"cut 60:00 from {start} s")
    to_hour_flac(src, d / "audio.flac", start)
    window = [x for x in lid if start <= x["t"] < start + HOUR]
    (d / "lid.json").write_text(json.dumps([{**x, "t": x["t"] - start} for x in window], indent=1))
    counts = {lang: sum(x["lang"] == lang for x in window) for lang in {x["lang"] for x in window}}
    return {"languages": ["ro", "ru"], "source": url, "window_start_s": start, "session_minutes": round(total / 60),
            "license": "public broadcast of the Parliament of the Republic of Moldova; used for internal testing only",
            "reference": None, "lid": "lid.json", "lid_minutes": counts,
            "note": "no reference text: multimedia.parlament.md answered 503 and old.parlament.md serves a script page "
                    "instead of the stenogram, so this hour tests speed, code-switching and the minutes, not CER"}


SOURCES = {"rompar_60": rompar, "icsi_60": icsi, "kremlin_60": kremlin, "md_parl_60": md_parl}


def main():
    threading.Thread(target=heartbeat, daemon=True).start()
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    manifest = {"built": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "duration_s": HOUR,
                "format": "FLAC, 16 kHz, mono", "hours": []}
    for sid, fn in SOURCES.items():
        STATE["source"] = sid
        d = OUT / sid
        d.mkdir(parents=True, exist_ok=True)
        t = time.time()
        try:
            entry = {"id": sid, "status": "ok", "audio": f"{sid}/audio.flac", "duration_s": HOUR, **fn(d)}
            for key in ("reference", "segments", "rttm", "chapters", "lid"):
                if entry.get(key):
                    entry[key] = f"{sid}/{entry[key]}"
            log(f"{sid}: OK in {(time.time() - t) / 60:.1f} min")
        except Exception as e:
            entry = {"id": sid, "status": "failed", "error": repr(e)[:500], "traceback": traceback.format_exc()[-2000:]}
            log(f"{sid}: FAILED {e!r}")
            shutil.rmtree(d, ignore_errors=True)
        entry["build_minutes"] = round((time.time() - t) / 60, 1)
        manifest["hours"].append(entry)
        STATE["done"] += 1
        (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        for f in TMP.iterdir():   # keep /tmp small between sources
            f.unlink() if f.is_file() else shutil.rmtree(f, ignore_errors=True)
    ok = [h["id"] for h in manifest["hours"] if h["status"] == "ok"]
    log(f"done: {len(ok)}/{len(SOURCES)} hours built: {', '.join(ok) or 'none'}")
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
