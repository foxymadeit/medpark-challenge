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
import zipfile
from pathlib import Path

T0 = time.time()
DATA = Path("/tmp/data")
WORK = Path("/kaggle/working")
REPO = Path("/tmp/repo")
PER_LABEL = 300   # cap pieces per speaker so no one voice dominates
random.seed(0)
socket.setdefaulttimeout(120)  # a stalled mirror raises and gets retried instead of hanging the run
STATE = {"phase": "start", "note": "", "progress": 0, "watch": True}


def log(msg):
    print(f"[{(time.time() - T0) / 60:6.1f} min] {msg}", flush=True)


def sh(cmd):
    log(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def phase(name, watch=True):
    """watch=False where the log has its own progress lines (training)."""
    STATE.update(phase=name, note="", watch=watch, progress=STATE["progress"] + 1)
    log(f"=== {name}")


def tick(note):
    STATE.update(note=note, progress=STATE["progress"] + 1)


def gpu_load():
    r = subprocess.run("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits",
                       shell=True, capture_output=True, text=True)
    rows = [x.split(",") for x in r.stdout.strip().splitlines() if "," in x]
    return " ".join(f"[{u.strip()}% {int(m) / 1024:.1f} GB]" for u, m in rows) or "n/a"


def ram_free():
    try:
        return f"{int(next(x for x in open('/proc/meminfo') if x.startswith('MemAvailable')).split()[1]) / 1e6:.1f} GB"
    except OSError:
        return "n/a"


def heartbeat(every=60, stall=600):
    """Once a minute: phase, current file, data on disk, free RAM and GPU load,
    to the log and to /kaggle/working/status.json. If a watched phase makes no
    progress for 10 minutes, print every thread's stack to show where it hangs."""
    last, since = None, time.time()
    while True:
        time.sleep(every)
        try:
            if STATE["progress"] != last:
                last, since = STATE["progress"], time.time()
            ram = ram_free()
            data = sum(f.stat().st_size for f in DATA.rglob("*") if f.is_file()) / 1e9 if DATA.exists() else 0.0
            msg = f"{STATE['phase']} | {STATE['note']} | data {data:.1f} GB | RAM free {ram} | GPU {gpu_load()}"
            log(f"heartbeat: {msg}")
            (WORK / "status.json").write_text(json.dumps({"minute": round((time.time() - T0) / 60, 1), **STATE, "status": msg}))
            if STATE["watch"] and time.time() - since > stall:
                log(f"no progress for {stall // 60} min in '{STATE['phase']}'; stack of every thread:")
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
    """Drop pieces that point at an unreadable file or run past its end. One
    bad slice would otherwise crash training an hour in."""
    import soundfile as sf
    length, keep, bad = {}, [], 0
    for it in items:
        if it[0] not in length:
            try:
                length[it[0]] = sf.info(it[0]).duration
            except Exception as e:
                length[it[0]] = -1.0
                log(f"unreadable {it[0]}: {e}")
        if it[1] + it[2] <= length[it[0]] + 0.01:
            keep.append(it)
        else:
            bad += 1
    log(f"checked {len(length)} audio files: kept {len(keep)} pieces, dropped {bad}")
    return keep


def setup():
    sh("nvidia-smi || true")
    sh("df -h /tmp /kaggle/working")
    sh('pip install -q "nemo_toolkit[asr]" onnx onnxruntime sherpa-onnx soundfile pyarrow')
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
    for i, m in enumerate(meetings):
        if i % 10 == 0:
            log(f"AMI meeting {i + 1}/{len(meetings)}, {len(out)} pieces so far")
        try:
            wav = fetch(f"https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/{m}/audio/{m}.Array1-01.wav",
                        DATA / "ami" / f"{m}.wav")
            rttm = fetch(f"{base}/only_words/rttms/train/{m}.rttm", DATA / "ami" / f"{m}.rttm")
        except RuntimeError as e:
            log(f"skip {m}: {e}")
            continue
        for spk, iv in clean_intervals(read_rttm(rttm)).items():
            out += [(str(wav), off, dur, f"ami_{spk}") for off, dur in pieces(iv, rng)]
    log(f"AMI: {len(out)} pieces")
    return out


def voxconverse():
    from eval.der import read_rttm
    from train.fit_backend import clean_intervals
    from train.make_manifest import pieces
    z = fetch("https://www.robots.ox.ac.uk/~vgg/data/voxconverse/data/voxconverse_dev_wav.zip", DATA / "vc_dev.zip")
    with zipfile.ZipFile(z) as f:
        f.extractall(DATA / "vc")
    sh(f"git clone -q --depth 1 https://github.com/joonson/voxconverse {DATA / 'vc_labels'}")
    wavs = {p.stem: p for p in (DATA / "vc").rglob("*.wav") if "__MACOSX" not in str(p)}
    out, rng = [], __import__("numpy").random.default_rng(1)
    for rttm in (DATA / "vc_labels" / "dev").glob("*.rttm"):
        wav = wavs.get(rttm.stem)
        if wav is None:
            continue
        for spk, iv in clean_intervals(read_rttm(rttm)).items():
            out += [(str(wav), off, dur, f"vc_{rttm.stem}_{spk}") for off, dur in pieces(iv, rng, cap=60)]
    log(f"VoxConverse dev: {len(out)} pieces")
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


def voxpopuli_ro():
    import io

    import pyarrow.parquet as pq
    import soundfile as sf
    from huggingface_hub import hf_hub_download
    path = hf_hub_download("facebook/voxpopuli", "ro/train-00000-of-00005.parquet", repo_type="dataset",
                           local_dir=DATA / "vp")
    out, n = [], 0
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
                tick(f"{n} clips")
    log(f"VoxPopuli RO: {len(out)} pieces")
    return out


def write_manifests(items):
    by = {}
    for it in items:
        by.setdefault(it[3], []).append(it)
    keep = []
    for label, xs in by.items():
        random.shuffle(xs)
        if len(xs) >= 8:  # need enough pieces to learn and to validate a voice
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
        "per_source": {src: sum(1 for x in train if x[3].startswith(src)) for src in ("ami_", "vc_", "ali_", "vp_ro_")},
    }, indent=2))


def check_onnx(path):
    import numpy as np
    import sherpa_onnx
    ex = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(path)))
    s = ex.create_stream()
    s.accept_waveform(sample_rate=16000, waveform=np.random.default_rng(0).standard_normal(32000).astype("float32") * 0.1)
    s.input_finished()
    log(f"sherpa-onnx loads {path.name}: dim {ex.dim}, embedding norm {np.linalg.norm(ex.compute(s)):.2f}")


def smoke():
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
       f"--val {d}/val.jsonl --epochs 1 --batch 4 --smoke --out {d}/smoke.onnx")
    check_onnx(d / "smoke.onnx")


def main():
    threading.Thread(target=heartbeat, daemon=True).start()
    phase("setup")
    setup()
    phase("smoke test: one batch, export, load")
    smoke()
    DATA.mkdir(parents=True, exist_ok=True)
    items = []
    for name, fn in (("AMI", ami), ("VoxPopuli RO", voxpopuli_ro), ("VoxConverse", voxconverse), ("AliMeeting", alimeeting)):
        phase(f"data: {name}")
        try:
            got = fn()
            describe(name, got)
            items += got
        except Exception as e:  # one source failing should not sink the run
            log(f"{name} failed, continuing without it: {e!r}")
    phase("check pieces")
    items = check_pieces(items)
    write_manifests(items)
    phase("train", watch=False)
    epochs = os.environ.get("EPOCHS", "8")
    sh(f"cd {REPO}/diarization && python train/finetune_titanet.py --train {DATA}/train.jsonl "
       f"--val {DATA}/val.jsonl --epochs {epochs} --out {WORK}/nemo_en_titanet_small_ft.onnx")
    phase("verify export")
    check_onnx(WORK / "nemo_en_titanet_small_ft.onnx")
    log("done")


if __name__ == "__main__":
    main()
