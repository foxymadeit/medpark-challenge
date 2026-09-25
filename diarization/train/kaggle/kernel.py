"""Kaggle GPU job: fine-tune TitaNet-small on open meeting and Romanian speech.

Pushed with `kaggle kernels push` from train/kaggle/. Everything is
downloaded here on Kaggle's side; nothing comes from the hospital. The
trained model lands in /kaggle/working/nemo_en_titanet_small_ft.onnx.

Training data (all public):
  AMI train, 136 meetings, far-field mic   CC BY 4.0   meetings, English
  AliMeeting Eval, far-field channel 0     CC BY-SA    meetings, Mandarin
  VoxConverse dev                          CC BY 4.0   many speakers per file
  VoxPopuli Romanian, one train shard      CC0         Romanian voices
Never trained on (kept for testing): AMI dev/test, NOTSOFAR, Medpark.
"""

import faulthandler
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import traceback
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

T0 = time.time()
DATA = Path("/tmp/data")
WORK = Path("/kaggle/working")
REPO = Path("/tmp/repo")
PER_LABEL = 300   # cap pieces per speaker so no one voice dominates
# "multilingual" (the second notebook) adds Russian and more Romanian from
# Common Voice, VoxConverse test, Simsamu medical calls and room echo.
PROFILE = os.environ.get("DATA_PROFILE", "base")
MULTI = PROFILE == "multilingual"
OUT_NAME = "nemo_titanet_small_multi.onnx" if MULTI else "nemo_en_titanet_small_ft.onnx"
MIN_PIECES = 5 if MULTI else 8   # Common Voice speakers have a median of 5 (RU) to 15 (RO) clips
random.seed(0)
socket.setdefaulttimeout(120)  # a stalled mirror raises and gets retried instead of hanging the run
# Planned minutes per phase, for the "how much is left" estimate. Once a phase
# reports a fraction done, its own speed replaces the plan; training reports
# through train_progress.json.
PLAN = {"setup": 1, "smoke": 5, "AMI": 25, "VoxPopuli RO": 6, "VoxConverse": 3, "AliMeeting": 6,
        "check": 2, "preflight": 2, "train": 60, "export": 1}
if MULTI:
    PLAN = {"setup": 1, "echo": 4, "smoke": 5, "AMI": 20, "VoxPopuli RO": 25, "VoxConverse": 3,
            "VoxConverse test": 5, "AliMeeting": 6, "CV Russian": 20, "CV Romanian": 10, "Simsamu": 2,
            "check": 4, "preflight": 2, "train": 180, "export": 1}
STATE = {"key": "setup", "phase": "start", "note": "", "frac": 0.0, "progress": 0, "watch": True,
         "t_phase": time.time(), "warnings": [], "phases": []}
TRAIN_PROGRESS = WORK / "train_progress.json"


def log(msg):
    print(f"[{(time.time() - T0) / 60:6.1f} min] {msg}", flush=True)


def sh(cmd):
    log(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def phase(key, label=None, watch=True):
    """watch=False where the log has its own progress lines (training)."""
    now = time.time()
    if STATE["phases"]:
        STATE["phases"][-1]["minutes"] = round((now - STATE["t_phase"]) / 60, 1)
    STATE["phases"].append({"phase": label or key, "minutes": None})
    STATE.update(key=key, phase=label or key, note="", frac=0.0, watch=watch, t_phase=now,
                 progress=STATE["progress"] + 1)
    log(f"=== phase {list(PLAN).index(key) + 1}/{len(PLAN)}: {label or key}")


def tick(note, frac=None):
    STATE.update(note=note, progress=STATE["progress"] + 1)
    if frac is not None:
        STATE["frac"] = frac


def spent_min():
    return (time.time() - T0) / 60


def warn(msg):
    log(f"WARNING: {msg}")
    STATE["warnings"] = (STATE["warnings"] + [f"{spent_min():.0f} min: {msg}"])[-20:]


def train_progress():
    try:
        return json.loads(TRAIN_PROGRESS.read_text())
    except (OSError, ValueError):
        return None


def minutes_left():
    keys = list(PLAN)
    key, frac = STATE["key"], STATE["frac"]
    tp = train_progress() if key == "train" else None
    spent = time.time() - STATE["t_phase"]
    if tp:
        here = tp["eta_min"] * 60
    else:
        here = spent * (1 - frac) / frac if frac > 0.05 else max(PLAN[key] * 60 - spent, 60)
    return here / 60 + sum(PLAN[k] for k in keys[keys.index(key) + 1:])


def gpu_load():
    """[(util %, memory GB)] per GPU; empty without nvidia-smi."""
    r = subprocess.run("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits",
                       shell=True, capture_output=True, text=True)
    return [(int(u), int(m) / 1024) for u, m in (x.split(",") for x in r.stdout.strip().splitlines() if "," in x)]


def ram_free():
    """GB available, or None off Linux."""
    try:
        return int(next(x for x in open("/proc/meminfo") if x.startswith("MemAvailable")).split()[1]) / 1e6
    except OSError:
        return None


def health(ram, gpus, idle_beats):
    """Problems worth a WARNING line right now; empty means OK."""
    out = []
    if ram is not None and ram < 1.5:
        out.append(f"only {ram:.1f} GB RAM free")
    if WORK.exists() and shutil.disk_usage(WORK).used / 1e9 > 15:
        out.append("/kaggle/working is over 15 of 20 GB")
    if STATE["key"] == "train":
        if idle_beats >= 3:
            out.append(f"GPU idle for {idle_beats} minutes during training")
        tp = train_progress()
        if tp and time.time() - tp["updated"] > 300:
            out.append(f"no training update for {(time.time() - tp['updated']) / 60:.0f} min")
        if tp and tp.get("warn"):
            out.append(tp["warn"])
    if time.time() - T0 > 10.5 * 3600:
        out.append("past 10.5 h; Kaggle stops runs at 12 h")
    return out


def heartbeat(every=60, stall=600):
    """Once a minute, one line: overall % done and minutes left, the phase and
    what it is on, data on disk, free RAM, GPU load, and OK or the problems.
    The same goes to /kaggle/working/status.json. If a watched phase makes no
    progress for 10 minutes, every thread's stack is printed to show the hang."""
    last, since, idle = None, time.time(), 0
    while True:
        time.sleep(every)
        try:
            if STATE["progress"] != last:
                last, since = STATE["progress"], time.time()
            ram, gpus = ram_free(), gpu_load()
            training = STATE["key"] == "train"  # the GPU is idle by design while data downloads
            idle = idle + 1 if training and gpus and all(u == 0 for u, _ in gpus) else 0
            data = sum(f.stat().st_size for f in DATA.rglob("*") if f.is_file()) / 1e9 if DATA.exists() else 0.0
            spent, left = (time.time() - T0) / 60, minutes_left()
            problems = health(ram, gpus, idle)
            if STATE["watch"] and time.time() - since > stall:
                problems.append(f"no progress for {(time.time() - since) / 60:.0f} min")
            for p in problems:  # keep each distinct problem once for run_report.json
                if not any(p in w for w in STATE["warnings"][-5:]):
                    STATE["warnings"] = (STATE["warnings"] + [f"{spent_min():.0f} min: {p}"])[-20:]
            where = f"phase {list(PLAN).index(STATE['key']) + 1}/{len(PLAN)} {STATE['phase']}"
            where += f": {STATE['note']}" if STATE["note"] else ""
            tp = train_progress() if STATE["key"] == "train" else None
            if tp:
                where += f": epoch {tp['epoch']}/{tp['epochs']}, step {tp['step']}/{tp['total']}, loss {tp['loss']:.3f}"
            msg = (f"{100 * spent / (spent + left):.0f}% done, about {left:.0f} min left | {where} | "
                   f"data {data:.1f} GB | RAM free {'n/a' if ram is None else f'{ram:.1f} GB'} | GPU "
                   + (" ".join(f"{u}% {m:.1f} GB" for u, m in gpus) or "n/a")
                   + " | " + ("OK" if not problems else "WARNING: " + "; ".join(problems)))
            log(f"[heartbeat] {msg}")
            (WORK / "status.json").write_text(json.dumps({"minute": round(spent, 1), "minutes_left": round(left),
                                                          "status": msg, **STATE}, indent=1))
            if STATE["watch"] and time.time() - since > stall:
                log("stack of every thread, to show where it hangs:")
                faulthandler.dump_traceback(all_threads=True)
                since = time.time()
        except Exception as e:  # the heartbeat must never take the run down
            log(f"heartbeat error: {e!r}")


def fetch(url, dest, tries=3):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    for i in range(tries):
        try:
            t = time.time()
            urllib.request.urlretrieve(url, dest)
            mb, took = dest.stat().st_size / 1e6, max(time.time() - t, 1e-3)
            if mb >= 1:
                log(f"got {dest.name}: {mb:.0f} MB in {took:.0f} s ({mb / took:.1f} MB/s)")
            tick(dest.name)
            return dest
        except Exception as e:  # network hiccups on big mirrors
            dest.unlink(missing_ok=True)
            log(f"retry {i + 1} for {url}: {e}")
            time.sleep(5)
    raise RuntimeError(f"could not download {url}")


def describe(name, xs):
    if not xs:
        log(f"{name}: no pieces")
        return
    d = sorted(x[2] for x in xs)
    log(f"{name}: {len(xs)} pieces, {len({x[3] for x in xs})} speakers, {sum(d) / 3600:.1f} h, "
        f"piece length {d[0]:.1f} / {d[len(d) // 2]:.1f} / {d[-1]:.1f} s (min / median / max)")


def check_pieces(items):
    """Drop pieces that point at an unreadable file or run past its end, and
    swap stereo or non-16 kHz files for a 16 kHz mono copy. Either would
    otherwise crash training an hour in; one stereo file stopped v3 and v4."""
    import soundfile as sf
    length, fixed, keep, bad = {}, {}, [], 0
    for path, off, dur, label in items:
        if path not in length:
            try:
                info = sf.info(path)
                length[path] = info.duration
                if info.channels != 1 or info.samplerate != 16000:
                    x, sr = sf.read(path, dtype="float32")
                    fixed[path] = str(Path(path).with_suffix("")) + ".mono16k.wav"
                    sf.write(fixed[path], to16k(x, sr), 16000)
                    log(f"converted to 16 kHz mono: {path} ({info.channels} ch, {info.samplerate} Hz)")
            except Exception as e:
                length[path] = -1.0
                log(f"unreadable {path}: {e}")
        if off + dur <= length[path] + 0.01:
            keep.append((fixed.get(path, path), off, dur, label))
        else:
            bad += 1
    log(f"checked {len(length)} audio files: {len(fixed)} converted to 16 kHz mono, "
        f"kept {len(keep)} pieces, dropped {bad}")
    return keep


def setup():
    sh("nvidia-smi || true")
    sh("df -h /tmp /kaggle/working")
    sh('pip install -q "nemo_toolkit[asr]" onnx onnxruntime sherpa-onnx soundfile pyarrow')
    if not (REPO / ".git").exists():  # the multilingual notebook clones it before handing over
        sh(f"git clone -q --depth 1 -b Coflazo-Branch https://github.com/foxymadeit/medpark-challenge {REPO}")
    sys.path.insert(0, str(REPO / "diarization"))


# ---------- datasets -> (audio_path, offset, duration, label) pieces ----------

def ami():
    from eval.der import read_rttm
    from train.fit_backend import clean_intervals
    from train.make_manifest import pieces
    base = "https://raw.githubusercontent.com/pyannote/AMI-diarization-setup/main"
    meetings = urllib.request.urlopen(f"{base}/lists/train.meetings.txt").read().decode().split()
    out, rng = [], __import__("numpy").random.default_rng(0)

    def get(m):
        try:
            return (m, fetch(f"https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/{m}/audio/{m}.Array1-01.wav",
                             DATA / "ami" / f"{m}.wav"),
                    fetch(f"{base}/only_words/rttms/train/{m}.rttm", DATA / "ami" / f"{m}.rttm"))
        except RuntimeError as e:
            log(f"skip {m}: {e}")
            return m, None, None

    log(f"AMI: {len(meetings)} meetings, 6 downloads at a time")
    with ThreadPoolExecutor(6) as pool:  # one at a time took 67 minutes in the first run
        for i, (m, wav, rttm) in enumerate(pool.map(get, meetings), 1):
            tick(f"{i}/{len(meetings)} meetings", frac=i / len(meetings))
            if i % 10 == 0:
                log(f"AMI {i}/{len(meetings)} meetings, {len(out)} pieces so far")
            if wav is None:
                continue
            for spk, iv in clean_intervals(read_rttm(rttm)).items():
                out += [(str(wav), off, dur, f"ami_{spk}") for off, dur in pieces(iv, rng)]
    log(f"AMI: {len(out)} pieces")
    return out


def voxconverse(split="dev"):
    from eval.der import read_rttm
    from train.fit_backend import clean_intervals
    from train.make_manifest import pieces
    z = fetch(f"https://www.robots.ox.ac.uk/~vgg/data/voxconverse/data/voxconverse_{split}_wav.zip",
              DATA / f"vc_{split}.zip")
    with zipfile.ZipFile(z) as f:
        f.extractall(DATA / f"vc_{split}")
    z.unlink()
    if not (DATA / "vc_labels").exists():
        sh(f"git clone -q --depth 1 https://github.com/joonson/voxconverse {DATA / 'vc_labels'}")
    wavs = {p.stem: p for p in (DATA / f"vc_{split}").rglob("*.wav") if "__MACOSX" not in str(p)}
    out, rng = [], __import__("numpy").random.default_rng(1 if split == "dev" else 11)
    for rttm in (DATA / "vc_labels" / split).glob("*.rttm"):
        wav = wavs.get(rttm.stem)
        if wav is None:
            continue
        for spk, iv in clean_intervals(read_rttm(rttm)).items():
            out += [(str(wav), off, dur, f"vc_{rttm.stem}_{spk}") for off, dur in pieces(iv, rng, cap=60)]
    log(f"VoxConverse {split}: {len(out)} pieces")
    return out


def textgrid_intervals(path):
    """speaker tier -> [(start, end)] for non-empty intervals (long TextGrid format)."""
    tiers, tier, cur = {}, None, {}
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if m := re.match(r'name = "(.*)"', line):
            tier = m.group(1)
            tiers.setdefault(tier, [])
        elif m := re.match(r"xmin = ([\d.]+)", line):
            cur = {"a": float(m.group(1))}
        elif m := re.match(r"xmax = ([\d.]+)", line):
            cur["b"] = float(m.group(1))
        elif (m := re.match(r'text = "(.*)"', line)) and tier and "a" in cur:
            if m.group(1).strip():
                tiers[tier].append((cur["a"], cur["b"]))
            cur = {}
    return tiers


def alimeeting():
    import soundfile as sf
    from train.fit_backend import clean_intervals
    from train.make_manifest import pieces
    tgz = fetch("https://speech-lab-share-data.oss-cn-shanghai.aliyuncs.com/AliMeeting/openlr/Eval_Ali.tar.gz",
                DATA / "Eval_Ali.tar.gz")
    with tarfile.open(tgz) as f:
        f.extractall(DATA / "ali", filter="data")
    out, rng = [], __import__("numpy").random.default_rng(2)
    for tg in (DATA / "ali").rglob("*far*/textgrid_dir/*.TextGrid"):
        audio = next((DATA / "ali").rglob(f"*far*/audio_dir/{tg.stem}*.wav"), None)
        if audio is None:
            continue
        x, sr = sf.read(audio, dtype="float32", always_2d=True)
        mono = DATA / "ali_mono" / f"{tg.stem}.wav"
        mono.parent.mkdir(parents=True, exist_ok=True)
        sf.write(mono, x[:, 0], sr)
        ref = [(spk, a, b) for spk, iv in textgrid_intervals(tg).items() for a, b in iv]
        for spk, iv in clean_intervals(ref).items():
            out += [(str(mono), off, dur, f"ali_{tg.stem}_{spk}") for off, dur in pieces(iv, rng)]
    shutil.rmtree(DATA / "ali", ignore_errors=True)
    log(f"AliMeeting eval: {len(out)} pieces")
    return out


def voxpopuli_ro(shards=1):
    import io

    import pyarrow.parquet as pq
    import soundfile as sf
    from huggingface_hub import hf_hub_download
    out, n = [], 0
    for shard in range(shards):
        path = hf_hub_download("facebook/voxpopuli", f"ro/train-0000{shard}-of-00005.parquet", repo_type="dataset",
                               local_dir=DATA / "vp")
        log(f"VoxPopuli RO: shard {shard + 1}/{shards}")
        n = _voxpopuli_shard(path, out, n, pq, sf, io)
        Path(path).unlink()
    log(f"VoxPopuli RO: {len(out)} pieces")
    return out


def _voxpopuli_shard(path, out, n, pq, sf, io):
    for batch in pq.ParquetFile(path).iter_batches(batch_size=256, columns=["audio", "speaker_id"]):
        for audio, spk in zip(batch.column("audio").to_pylist(), batch.column("speaker_id").to_pylist()):
            if not spk or spk == "None":
                continue
            x, sr = sf.read(io.BytesIO(audio["bytes"]), dtype="float32")
            dur = len(x) / sr
            if dur < 1.5:
                continue
            wav = DATA / "vp_wav" / f"{n}.wav"
            wav.parent.mkdir(parents=True, exist_ok=True)
            sf.write(wav, x, sr)
            out.append((str(wav), 0.0, round(min(dur, 3.0), 3), f"vp_ro_{spk}"))
            n += 1
            if n % 1000 == 0:
                log(f"VoxPopuli RO: {n} clips written")
                tick(f"{n} clips", frac=min(n / (25000 if MULTI else 5000), 0.95))
    return n


def to16k(x, sr):
    """Mono float32 at 16 kHz (Common Voice mp3s come at 32 or 48 kHz)."""
    from math import gcd

    from scipy.signal import resample_poly
    x = x.mean(axis=1) if x.ndim == 2 else x
    if sr != 16000:
        g = gcd(16000, sr)
        x = resample_poly(x, 16000 // g, sr // g)
    return x.astype("float32")


def _cv_clip(job):
    import soundfile as sf
    src, dst = job
    try:
        x, sr = sf.read(src, dtype="float32")
        x = to16k(x, sr)
        sf.write(dst, x, 16000)
        return dst, len(x) / 16000
    except Exception:  # a broken clip is dropped, not fatal
        return dst, 0.0


CV_REPO = "fsicoli/common_voice_22_0"   # ungated mirror of Common Voice 22, CC0


def common_voice(lang):
    """Every clip of the train, dev, test and other splits, labelled by the
    speaker's client_id, decoded to 16 kHz wav, one piece of up to 3 s each."""
    import csv

    from huggingface_hub import HfApi, hf_hub_download
    from train.holdout import held_out  # every tenth speaker builds the mixed-language test instead
    csv.field_size_limit(10**9)
    root = DATA / f"cv_{lang}"
    files = HfApi().list_repo_files(CV_REPO, repo_type="dataset")
    who = {}
    for split in ("train", "dev", "test", "other"):
        tsv = hf_hub_download(CV_REPO, f"transcript/{lang}/{split}.tsv", repo_type="dataset", local_dir=root)
        with open(tsv, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
                who[r["path"]] = r["client_id"]
        for tar in (x for x in files if x.startswith(f"audio/{lang}/{split}/") and x.endswith(".tar")):
            t = Path(hf_hub_download(CV_REPO, tar, repo_type="dataset", local_dir=root))
            log(f"CV {lang}: got {tar} ({t.stat().st_size / 1e6:.0f} MB)")
            with tarfile.open(t) as f:
                f.extractall(root / "mp3", filter="data")
            t.unlink()
            tick(tar)
    (root / "wav").mkdir(exist_ok=True)
    mp3s = [p for p in (root / "mp3").rglob("*.mp3") if p.name in who]
    held = {who[p.name] for p in mp3s if held_out(who[p.name])}
    jobs = [(str(p), str(root / "wav" / f"{p.stem}.wav")) for p in mp3s if who[p.name] not in held]
    speaker = {str(root / "wav" / f"{p.stem}.wav"): who[p.name] for p in mp3s}
    log(f"CV {lang}: {len(mp3s)} clips from {len(set(who[p.name] for p in mp3s))} speakers; "
        f"{len(held)} speakers held out for the mixed-language test; decoding {len(jobs)} clips")
    out = []
    with ThreadPoolExecutor(8) as pool:
        for i, (dst, dur) in enumerate(pool.map(_cv_clip, jobs), 1):
            if dur >= 1.5:
                out.append((dst, 0.0, round(min(dur, 3.0), 3), f"cv_{lang}_{speaker[dst][:20]}"))
            if i % 2000 == 0:
                tick(f"decoded {i}/{len(jobs)} clips", frac=i / len(jobs))
            if i % 10000 == 0:
                log(f"CV {lang}: decoded {i}/{len(jobs)} clips")
    shutil.rmtree(root / "mp3", ignore_errors=True)
    heldout = WORK / "heldout_speakers.json"
    record = json.loads(heldout.read_text()) if heldout.exists() else {}
    record[lang] = sorted(held)
    heldout.write_text(json.dumps(record))
    return out


def hold_out_bilingual(items):
    """People who recorded both Romanian and Russian are the one real test of
    'same person, two languages, one label', so none of them trains."""
    by = {"ru": set(), "ro": set()}
    for x in items:
        if x[3].startswith(("cv_ru_", "cv_ro_")):
            by[x[3][3:5]].add(x[3][6:])
    both = by["ru"] & by["ro"]
    heldout = WORK / "heldout_speakers.json"
    record = json.loads(heldout.read_text()) if heldout.exists() else {}
    record["bilingual_ro_ru"] = sorted(both)
    heldout.write_text(json.dumps(record))
    log(f"held out {len(both)} speakers who recorded both Romanian and Russian")
    return [x for x in items if not (x[3].startswith(("cv_ru_", "cv_ro_")) and x[3][6:] in both)]


def simsamu():
    """Simsamu (MIT): simulated French emergency medical calls with speaker turns."""
    import io

    import numpy as np
    import pyarrow.parquet as pq
    import soundfile as sf
    from huggingface_hub import hf_hub_download
    from train.fit_backend import clean_intervals
    from train.make_manifest import pieces
    path = hf_hub_download("diarizers-community/simsamu", "data/train-00000-of-00001.parquet",
                           repo_type="dataset", local_dir=DATA / "simsamu")
    t = pq.read_table(path)
    out, rng = [], np.random.default_rng(3)
    cols = (t.column(c).to_pylist() for c in ("audio", "timestamps_start", "timestamps_end", "speakers"))
    for n, (audio, starts, ends, spk) in enumerate(zip(*cols)):
        x, sr = sf.read(io.BytesIO(audio["bytes"]), dtype="float32")
        wav = DATA / "simsamu" / f"{n}.wav"
        sf.write(wav, to16k(x, sr), 16000)
        for who, iv in clean_intervals(list(zip(spk, starts, ends))).items():
            out += [(str(wav), off, dur, f"sim_{n}_{who}") for off, dur in pieces(iv, rng)]
    return out


def room_echo():
    """OpenSLR 28 (Apache 2.0): simulated medium-room impulse responses and
    point-source noises, so close-mic clips sound like a meeting room."""
    import soundfile as sf
    z = fetch("https://www.openslr.org/resources/28/rirs_noises.zip", DATA / "rirs_noises.zip")
    with zipfile.ZipFile(z) as f:
        f.extractall(DATA / "echo")
    z.unlink()
    paths = {}
    for kind, pattern, min_dur in (("rir", "mediumroom/*/*.wav", 0.0), ("noise", "pointsource_noises/*.wav", 3.5)):
        rows = []
        for p in sorted((DATA / "echo").rglob(pattern)):
            info = sf.info(p)
            d = info.duration
            if d >= min_dur and info.channels == 1:  # a noise must cover a whole 3 s mono piece
                rows.append(json.dumps({"audio_filepath": str(p), "duration": d, "offset": 0.0, "text": ""}))
        paths[kind] = DATA / f"{kind}.jsonl"
        paths[kind].write_text("\n".join(rows) + "\n")
        log(f"room echo: {len(rows)} {kind} files")
    return paths["rir"], paths["noise"]


def write_manifests(items):
    by = {}
    for it in items:
        by.setdefault(it[3], []).append(it)
    keep = []
    for label, xs in by.items():
        random.shuffle(xs)
        if len(xs) >= MIN_PIECES:  # need enough pieces to learn and to validate a voice
            keep += xs[:PER_LABEL]
    random.shuffle(keep)
    n_val = max(500, len(keep) // 30)
    val, train = keep[:n_val], keep[n_val:]
    labels = {x[3] for x in train}
    val = [x for x in val if x[3] in labels]
    for name, xs in (("train", train), ("val", val)):
        with open(DATA / f"{name}.jsonl", "w") as f:
            for a, off, dur, lab in xs:
                f.write(json.dumps({"audio_filepath": a, "offset": off, "duration": dur, "label": lab}) + "\n")
    log(f"manifests: {len(train)} train / {len(val)} val pieces, {len(labels)} speakers")
    (WORK / "data_summary.json").write_text(json.dumps({
        "train_pieces": len(train), "val_pieces": len(val), "speakers": len(labels),
        "per_source": {src: sum(1 for x in train if x[3].startswith(src)) for src in ("ami_", "vc_", "ali_", "vp_ro_", "cv_ru_", "cv_ro_", "sim_")},
    }, indent=2))


def check_onnx(path):
    import numpy as np
    import sherpa_onnx
    ex = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(path)))
    s = ex.create_stream()
    s.accept_waveform(sample_rate=16000, waveform=np.random.default_rng(0).standard_normal(32000).astype("float32") * 0.1)
    s.input_finished()
    log(f"sherpa-onnx loads {path.name}: dim {ex.dim}, embedding norm {np.linalg.norm(ex.compute(s)):.2f}")


def smoke(aug=""):
    """Two fake voices, one batch, then export. Catches config and export
    errors in a couple of minutes instead of after the long download."""
    import numpy as np
    import soundfile as sf
    d = Path("/tmp/smoke")
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    t = np.arange(32000) / 16000
    rows = []
    for spk in range(2):
        for i in range(6):
            wav = d / f"s{spk}_{i}.wav"
            x = 0.1 * np.sin(2 * np.pi * (150 + 100 * spk) * t) + 0.01 * rng.standard_normal(t.size)
            sf.write(wav, x.astype("float32"), 16000)
            rows.append({"audio_filepath": str(wav), "offset": 0.0, "duration": 2.0, "label": f"smoke_{spk}"})
    for name in ("train", "val"):
        (d / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    sh(f"cd {REPO}/diarization && python train/finetune_titanet.py --train {d}/train.jsonl "
       f"--val {d}/val.jsonl --epochs 1 --batch 4 --smoke --out {d}/smoke.onnx {aug} --aug-prob 1.0")
    check_onnx(d / "smoke.onnx")


def report(result):
    """run_report.json: how each phase went, every warning, and the outcome.
    Written on success and on failure, so `kaggle kernels output` always has it."""
    if STATE["phases"] and STATE["phases"][-1]["minutes"] is None:
        STATE["phases"][-1]["minutes"] = round((time.time() - STATE["t_phase"]) / 60, 1)
    rep = {"result": result, "total_minutes": round((time.time() - T0) / 60, 1), "phases": STATE["phases"],
           "warnings": STATE["warnings"], "last_training_update": train_progress()}
    (WORK / "run_report.json").write_text(json.dumps(rep, indent=2))
    log(f"run report: {json.dumps(rep)}")


def run():
    threading.Thread(target=heartbeat, daemon=True).start()
    phase("setup", f"setup ({PROFILE} data)")
    setup()
    DATA.mkdir(parents=True, exist_ok=True)
    aug = ""
    if MULTI:
        phase("echo", "room echo and noise pack")
        rir, noise = room_echo()
        aug = f"--rir-manifest {rir} --noise-manifest {noise}"
    phase("smoke", "smoke test: one batch, export, load")
    smoke(aug)
    items = []
    sources = [("AMI", ami), ("VoxPopuli RO", voxpopuli_ro), ("VoxConverse", voxconverse), ("AliMeeting", alimeeting)]
    if MULTI:
        sources = [("AMI", ami), ("VoxPopuli RO", lambda: voxpopuli_ro(shards=5)), ("VoxConverse", voxconverse),
                   ("VoxConverse test", lambda: voxconverse("test")), ("AliMeeting", alimeeting),
                   ("CV Russian", lambda: common_voice("ru")), ("CV Romanian", lambda: common_voice("ro")),
                   ("Simsamu", simsamu)]
    for name, fn in sources:
        phase(name, f"data: {name}")
        try:
            got = fn()
            describe(name, got)
            items += got
        except Exception as e:  # one source failing should not sink the run
            warn(f"{name} failed, continuing without it: {e!r}")
    if MULTI:
        items = hold_out_bilingual(items)
    phase("check", "check pieces")
    items = check_pieces(items)
    write_manifests(items)
    phase("preflight", "preflight: one real batch on the real data")
    sh(f"cd {REPO}/diarization && python train/finetune_titanet.py --train {DATA}/train.jsonl "
       f"--val {DATA}/val.jsonl --epochs 1 --smoke --out /tmp/preflight.onnx {aug}")
    phase("train", watch=False)
    epochs = os.environ.get("EPOCHS", "6" if MULTI else "8")
    sh(f"cd {REPO}/diarization && python train/finetune_titanet.py --train {DATA}/train.jsonl "
       f"--val {DATA}/val.jsonl --epochs {epochs} --out {WORK}/{OUT_NAME} "
       f"--progress {TRAIN_PROGRESS} {aug}")
    phase("export", "verify export")
    check_onnx(WORK / OUT_NAME)


def main():
    try:
        run()
    except BaseException as e:
        log(f"FAILED in phase '{STATE['phase']}' after {(time.time() - T0) / 60:.1f} min: {e!r}")
        traceback.print_exc()
        report(f"failed in {STATE['phase']}: {e!r}")
        raise
    report("done")
    log("done")


if __name__ == "__main__":
    main()
