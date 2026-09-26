"""Kaggle T4: zero-shot ASR candidates on every test set we have, before any training.

Dev-time only (Internet ON for installs, weights and public test sets). Each model
runs alone on GPU 0, so timings match the one-16-GB-GPU reference box.

Test sets (first N utterances each, fixed order):
  gold        Medpark 0:00-3:01, hand-corrected (asr-llm/data/gold_0-181s.txt), one long clip
  rompar_md   ROMPAR test, Moldovan speakers        rompar_ro  ROMPAR test, Romanian speakers
  fleurs_ro / fleurs_ru / fleurs_en                 FLEURS test, read speech
  cs_ru_en    CS-FLEURS read test, real Russian-English code-switching
  cs_ro_en    CS-FLEURS MMS test, concatenative Romanian-English code-switching
Timing: the full 11:42 Medpark file and a 60-minute file built from it.

Push from the repo root:  kaggle kernels push -p asr-llm/scripts/kaggle_asr_zeroshot
"""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import tarfile
import time
import traceback
from pathlib import Path

WORK = Path("/kaggle/working")
OUT = WORK / "out"
DATA = WORK / "data"
REPO = WORK / "repo"
N = int(os.environ.get("BENCH_N", "200"))
OUT.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

# Language each test set is mostly in: Canary needs it named; the others ignore it.
MATRIX = {
    "gold": "ro", "rompar_md": "ro", "rompar_ro": "ro", "fleurs_ro": "ro",
    "fleurs_ru": "ru", "fleurs_en": "en", "cs_ru_en": "ru", "cs_ro_en": "ro",
}


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def save(name: str, payload) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", name, flush=True)


def wav16k(src: Path | str, dest: Path, extra: str = "") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    sh(f"ffmpeg -nostdin -loglevel error -y -i '{src}' {extra} -ac 1 -ar 16000 '{dest}'")
    return dest


# ---------------------------------------------------------------- data

def build_sets() -> dict[str, list[dict]]:
    from huggingface_hub import hf_hub_download, snapshot_download
    import soundfile as sf

    sets: dict[str, list[dict]] = {}
    medpark = next(Path("/kaggle/input").rglob("*.m4a"))

    gold_lines = (REPO / "asr-llm/data/gold_0-181s.txt").read_text(encoding="utf-8").splitlines()
    gold_text = " ".join(l for l in gold_lines if l.strip() and not l.lstrip().startswith("#"))
    sets["gold"] = [{"audio": str(wav16k(medpark, DATA / "gold.wav", "-t 181")), "text": gold_text}]

    full = wav16k(medpark, DATA / "medpark_full.wav")
    hour = DATA / "medpark_60min.wav"
    sh(f"ffmpeg -nostdin -loglevel error -y -stream_loop 5 -i '{full}' -t 3600 -c copy '{hour}'")

    # ROMPAR test, split by dialect label.
    import pyarrow.parquet as pq

    table = pq.read_table(hf_hub_download("avramandrei/rompar", "data/test-00000-of-00001.parquet", repo_type="dataset"))
    md, ro = [], []
    for row in table.to_pylist():
        bucket = md if "mold" in str(row["dialect"]).lower() else ro
        if len(bucket) >= N:
            continue
        data, sr = sf.read(io.BytesIO(row["audio"]["bytes"]))
        path = DATA / "rompar" / f"{row['record_id']}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, data, sr)
        bucket.append({"audio": str(wav16k(path, path.with_suffix(".16k.wav"))), "text": row["transcript"]})
    sets["rompar_md"], sets["rompar_ro"] = md, ro

    # FLEURS test: raw transcription keeps case and punctuation.
    for lang, code in (("ro", "ro_ro"), ("ru", "ru_ru"), ("en", "en_us")):
        tsv = hf_hub_download("google/fleurs", f"data/{code}/test.tsv", repo_type="dataset")
        rows = list(csv.reader(open(tsv, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))[:N]
        wanted = {r[1]: r[2] for r in rows}
        tar = hf_hub_download("google/fleurs", f"data/{code}/audio/test.tar.gz", repo_type="dataset")
        items = []
        with tarfile.open(tar) as tf:
            for member in tf:
                name = Path(member.name).name
                if name in wanted:
                    dest = DATA / "fleurs" / lang / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(tf.extractfile(member).read())
                    items.append({"audio": str(dest), "text": wanted[name]})
        sets[f"fleurs_{lang}"] = items

    # CS-FLEURS: real read ru-en, concatenative ro-en.
    root = Path(snapshot_download(
        "byan/cs-fleurs", repo_type="dataset",
        allow_patterns=["read/test/metadata.jsonl", "read/test/audio/rus/*",
                        "mms/test/metadata.jsonl", "mms/test/audio/cs_ron_eng*/*"],
    ))
    for name, sub, lang in (("cs_ru_en", "read/test", "rus-eng"), ("cs_ro_en", "mms/test", "ron-eng")):
        rows = [json.loads(l) for l in open(root / sub / "metadata.jsonl", encoding="utf-8")]
        rows = [r for r in rows if r["language"] == lang][:N]
        sets[name] = [{"audio": str(wav16k(root / sub / r["file_name"], DATA / "cs" / f"{r['id']}.wav")), "text": r["text"]} for r in rows]

    save("sets.json", {k: len(v) for k, v in sets.items()})
    (WORK / "sets.json").write_text(json.dumps(sets, ensure_ascii=False))
    return sets


# ---------------------------------------------------------------- scoring

def _fold(text: str) -> str:
    """Same normalisation as asr_llm.clean._fold. Copied: importing asr_llm switches
    Hugging Face offline for the whole process, which would block the model downloads."""
    import re

    text = re.sub(r"[^\w\s]", " ", text.casefold().strip(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def edit_distance(ref: list, hyp: list) -> int:
    """Same as asr_llm.score.edit_distance (two-row Levenshtein)."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def score(refs: list[str], hyps: list[str]) -> dict:
    ce = cn = we = wn = 0
    for r, h in zip(refs, hyps):
        r, h = _fold(r), _fold(h or "")
        ce += edit_distance(list(r), list(h)); cn += len(r)
        we += edit_distance(r.split(), h.split()); wn += len(r.split())
    return {"cer": round(ce / max(cn, 1), 4), "wer": round(we / max(wn, 1), 4), "n": len(refs)}


# ---------------------------------------------------------------- models

def nemo_model(kind: str):
    import torch
    from nemo.collections.asr.models import ASRModel

    if kind == "jackrabbit":
        from huggingface_hub import hf_hub_download

        model = ASRModel.restore_from(hf_hub_download("surogate/jackrabbit-110m-ro", "jackrabbit-110m-ro.nemo"))
    else:
        model = ASRModel.from_pretrained({"parakeet": "nvidia/parakeet-tdt-0.6b-v3", "canary": "nvidia/canary-1b-v2"}[kind])
    return model.to(torch.device("cuda:0")).eval()


def nemo_transcribe(model, kind: str, paths: list[str], lang: str, batch: int = 16) -> list[str]:
    kwargs = {"source_lang": lang, "target_lang": lang} if kind == "canary" else {}
    out = model.transcribe(paths, batch_size=batch, **kwargs)
    return [o.text if hasattr(o, "text") else str(o) for o in out]


def run_nemo(kind: str, sets: dict[str, list[dict]]) -> None:
    import torch

    t0 = time.perf_counter()
    model = nemo_model(kind)
    result = {"load_s": round(time.perf_counter() - t0, 1), "sets": {}}
    for name, items in sets.items():
        if kind == "jackrabbit" and MATRIX[name] != "ro":
            continue
        paths = [i["audio"] for i in items]
        long = name == "gold"
        if long and kind == "parakeet":
            model.change_attention_model("rel_pos_local_attn", [256, 256])
            model.change_subsampling_conv_chunking_factor(1)
        t0 = time.perf_counter()
        hyps = nemo_transcribe(model, kind, paths, MATRIX[name], batch=1 if long else 16)
        seconds = time.perf_counter() - t0
        result["sets"][name] = {**score([i["text"] for i in items], hyps), "seconds": round(seconds, 1)}
        save(f"hyp_{kind}_{name}.json", [{"ref": i["text"], "hyp": h} for i, h in zip(items, hyps)])
        if long and kind == "parakeet":
            model.change_attention_model("rel_pos", [-1, -1])
    # Long-form speed: the full 11:42 file and 60 minutes, one pass each.
    if kind != "jackrabbit":
        if kind == "parakeet":
            model.change_attention_model("rel_pos_local_attn", [256, 256])
            model.change_subsampling_conv_chunking_factor(1)
        for label, path, secs in (("medpark_11m42", DATA / "medpark_full.wav", 702.5), ("medpark_60min", DATA / "medpark_60min.wav", 3600.0)):
            t0 = time.perf_counter()
            nemo_transcribe(model, kind, [str(path)], "ro", batch=1)
            took = time.perf_counter() - t0
            result[label] = {"seconds": round(took, 1), "rtfx": round(secs / took, 1)}
            save(f"result_{kind}.json", result)
    save(f"result_{kind}.json", result)
    del model
    torch.cuda.empty_cache()


def whisper_child() -> None:
    """Current pipeline's ASR (Whisper large-v3, ro+ru decodes). Own process: asr_llm switches HF offline."""
    sys.path.insert(0, str(REPO / "asr-llm"))
    os.environ.update(MOM_DEVICE="cuda", MOM_ASR_COMPUTE_TYPE="int8_float16", MOM_ASR_MODEL_DIR=str(REPO / "asr-llm/models/whisper"))
    import numpy as np

    from asr_llm.asr import WhisperAsr
    from asr_llm.audio import decode_audio
    from asr_llm.pipeline import transcribe_audio

    sets = json.loads((WORK / "sets.json").read_text())
    engine, result = WhisperAsr(), {"sets": {}}
    for name, items in sets.items():
        t0 = time.perf_counter()
        if name == "gold":
            transcript, _ = transcribe_audio(Path(items[0]["audio"]))
            hyps = [" ".join(s.text for s in transcript.segments)]
        else:
            hyps = [engine.transcribe_batch(decode_audio(Path(i["audio"])).astype(np.float32))[0] for i in items]
        result["sets"][name] = {**score([i["text"] for i in items], hyps), "seconds": round(time.perf_counter() - t0, 1)}
        save("result_whisper.json", result)


def run(name: str, fn, *args) -> None:
    try:
        fn(*args)
    except Exception:
        (OUT / f"{name}.error.txt").write_text(traceback.format_exc())
        traceback.print_exc()


if __name__ == "__main__":
    if sys.argv[1:2] == ["whisper"]:
        whisper_child()
        sys.exit(0)
    sh(f"git clone -q --depth 1 -b samoilov-asr-llm https://github.com/foxymadeit/medpark-challenge {REPO}")
    sh("pip install -q 'nemo_toolkit[asr]' huggingface_hub soundfile pyarrow")
    sets = build_sets()
    for kind in ("parakeet", "canary", "jackrabbit"):
        run(kind, run_nemo, kind, sets)
    sh(f"pip install -q -e {REPO}/asr-llm[asr] && cd {REPO}/asr-llm && python scripts/fetch_whisper.py large-v3")
    script = globals().get("__file__") or sys.argv[0]
    run("whisper", sh, f"{sys.executable} {script} whisper")
