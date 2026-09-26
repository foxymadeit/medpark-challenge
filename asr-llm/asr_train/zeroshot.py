"""Zero-shot ASR candidates on every test set we have, before (and after) any training.

Each model runs alone on one GPU, so timings match the one-16-GB-GPU reference box.

Test sets (first N utterances each, fixed order):
  gold        Medpark 0:00-3:01, hand-corrected (data/gold_0-181s.txt), one long clip
  rompar_md   ROMPAR test, Moldovan speakers        rompar_ro  ROMPAR test, Romanian speakers
  fleurs_ro / fleurs_ru / fleurs_en                 FLEURS test, read speech
  cs_ru_en    CS-FLEURS read test, real Russian-English code-switching
  cs_ro_en    CS-FLEURS MMS test, concatenative Romanian-English code-switching
Timing: the full Medpark file and a 60-minute file built from it.
gold and timing need --audio; without it they are skipped.

    python -m asr_train.zeroshot --work runs/zeroshot --audio ../data/Medpark_audio.m4a
    python -m asr_train.zeroshot --work runs/zeroshot --models parakeet \\
        --model-path parakeet=runs/ft/parakeet-tdt-0.6b-v3-medpark.nemo       # score the fine-tune
    python -m asr_train.zeroshot --work runs/zeroshot --hf-mirror ~/hf-mirror  # offline test sets

Writes <work>/out/: sets.json, result_<model>.json, hyp_<model>_<set>.json, <model>.error.txt.
Test sets are built once into <work>/data and reused; --rebuild-sets builds them again.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import tarfile
import time
import traceback
from pathlib import Path

from .common import ASR_ROOT, GOLD, ffmpeg_16k, gold_text, sh
from .hub import Hub
from .metrics import score

# Language each test set is mostly in: Canary needs it named; the others ignore it.
MATRIX = {
    "gold": "ro", "rompar_md": "ro", "rompar_ro": "ro", "fleurs_ro": "ro",
    "fleurs_ru": "ru", "fleurs_en": "en", "cs_ru_en": "ru", "cs_ro_en": "ro",
}
NEMO_MODELS = {"parakeet": "nvidia/parakeet-tdt-0.6b-v3", "canary": "nvidia/canary-1b-v2"}
MODELS = ("parakeet", "canary", "jackrabbit", "whisper")
RO_ONLY = {"jackrabbit"}  # Romanian-only model: skip ru/en sets


class Bench:
    def __init__(self, work: Path):
        self.work = work
        self.out = work / "out"
        self.data = work / "data"
        self.out.mkdir(parents=True, exist_ok=True)
        self.data.mkdir(parents=True, exist_ok=True)

    @property
    def sets_file(self) -> Path:
        return self.work / "sets.json"

    def save(self, name: str, payload) -> None:
        (self.out / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print("saved", name, flush=True)

    def timing_files(self) -> list[tuple[str, Path]]:
        return [(label, self.data / f"{label}.wav") for label in ("medpark_full", "medpark_60min") if (self.data / f"{label}.wav").exists()]


# ---------------------------------------------------------------- data

def build_sets(bench: Bench, hub: Hub, n: int, wanted: list[str], audio: Path | None, gold: Path, gold_s: float) -> dict[str, list[dict]]:
    sets: dict[str, list[dict]] = {}
    data = bench.data

    if audio:
        if "gold" in wanted:
            sets["gold"] = [{"audio": str(ffmpeg_16k(audio, data / "gold.wav", "-t", str(gold_s))), "text": gold_text(gold)}]
        full = ffmpeg_16k(audio, data / "medpark_full.wav")
        sh(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-stream_loop", "-1", "-i", str(full),
            "-t", "3600", "-c", "copy", str(data / "medpark_60min.wav")])
    elif "gold" in wanted:
        print("no --audio: gold set and long-form timing skipped", flush=True)

    if {"rompar_md", "rompar_ro"} & set(wanted):
        import pyarrow.parquet as pq
        import soundfile as sf

        table = pq.read_table(hub.file("avramandrei/rompar", "data/test-00000-of-00001.parquet"))
        md, ro = [], []
        for row in table.to_pylist():
            bucket = md if "mold" in str(row["dialect"]).lower() else ro
            if len(bucket) >= n:
                continue
            wave, sr = sf.read(io.BytesIO(row["audio"]["bytes"]))
            path = data / "rompar" / f"{row['record_id']}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(path, wave, sr)
            bucket.append({"audio": str(ffmpeg_16k(path, path.with_suffix(".16k.wav"))), "text": row["transcript"]})
        sets["rompar_md"], sets["rompar_ro"] = md, ro

    # FLEURS test: raw transcription keeps case and punctuation.
    for lang, code in (("ro", "ro_ro"), ("ru", "ru_ru"), ("en", "en_us")):
        if f"fleurs_{lang}" not in wanted:
            continue
        with open(hub.file("google/fleurs", f"data/{code}/test.tsv"), encoding="utf-8") as f:
            rows = list(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE))[:n]
        text = {r[1]: r[2] for r in rows}
        items = []
        with tarfile.open(hub.file("google/fleurs", f"data/{code}/audio/test.tar.gz")) as tf:
            for member in tf:
                name = Path(member.name).name
                if name in text:
                    dest = data / "fleurs" / lang / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(tf.extractfile(member).read())
                    items.append({"audio": str(dest), "text": text[name]})
        sets[f"fleurs_{lang}"] = items

    # CS-FLEURS: real read ru-en, concatenative ro-en.
    cs = [(name, sub, lang) for name, sub, lang in (("cs_ru_en", "read/test", "rus-eng"), ("cs_ro_en", "mms/test", "ron-eng")) if name in wanted]
    if cs:
        root = hub.snapshot("byan/cs-fleurs", ["read/test/metadata.jsonl", "read/test/audio/rus/*",
                                               "mms/test/metadata.jsonl", "mms/test/audio/cs_ron_eng*/*"])
        for name, sub, lang in cs:
            with open(root / sub / "metadata.jsonl", encoding="utf-8") as f:
                rows = [r for r in map(json.loads, f) if r["language"] == lang][:n]
            sets[name] = [{"audio": str(ffmpeg_16k(root / sub / r["file_name"], data / "cs" / f"{r['id']}.wav")), "text": r["text"]} for r in rows]

    sets = {k: sets[k] for k in MATRIX if k in sets}  # fixed order
    bench.save("sets.json", {k: len(v) for k, v in sets.items()})
    bench.sets_file.write_text(json.dumps(sets, ensure_ascii=False))
    return sets


# ---------------------------------------------------------------- models

def nemo_model(kind: str, hub: Hub, path: str | None, device: str):
    import torch
    from nemo.collections.asr.models import ASRModel

    if path:
        model = ASRModel.restore_from(str(Path(path).expanduser()))
    elif kind == "jackrabbit":
        model = ASRModel.restore_from(str(hub.file("surogate/jackrabbit-110m-ro", "jackrabbit-110m-ro.nemo", repo_type="model")))
    else:
        model = ASRModel.from_pretrained(NEMO_MODELS[kind])
    return model.to(torch.device(device)).eval()


def nemo_transcribe(model, kind: str, paths: list[str], lang: str, batch: int = 16) -> list[str]:
    kwargs = {"source_lang": lang, "target_lang": lang} if kind == "canary" else {}
    out = model.transcribe(paths, batch_size=batch, **kwargs)
    return [o.text if hasattr(o, "text") else str(o) for o in out]


def long_form(model, kind: str, on: bool) -> None:
    """Parakeet needs local attention and chunked subsampling for minutes-long clips on 16 GB."""
    if kind != "parakeet":
        return
    if on:
        model.change_attention_model("rel_pos_local_attn", [256, 256])
        model.change_subsampling_conv_chunking_factor(1)
    else:
        model.change_attention_model("rel_pos", [-1, -1])


def run_nemo(bench: Bench, hub: Hub, kind: str, sets: dict[str, list[dict]], path: str | None, device: str) -> None:
    import torch

    t0 = time.perf_counter()
    model = nemo_model(kind, hub, path, device)
    result = {"model": path or NEMO_MODELS.get(kind, kind), "load_s": round(time.perf_counter() - t0, 1), "sets": {}}
    for name, items in sets.items():
        if kind in RO_ONLY and MATRIX[name] != "ro":
            continue
        long = name == "gold"
        long_form(model, kind, long)
        t0 = time.perf_counter()
        hyps = nemo_transcribe(model, kind, [i["audio"] for i in items], MATRIX[name], batch=1 if long else 16)
        seconds = time.perf_counter() - t0
        result["sets"][name] = {**score([i["text"] for i in items], hyps), "seconds": round(seconds, 1)}
        bench.save(f"hyp_{kind}_{name}.json", [{"ref": i["text"], "hyp": h} for i, h in zip(items, hyps)])
        if long:
            long_form(model, kind, False)
        bench.save(f"result_{kind}.json", result)
    if kind not in RO_ONLY:
        long_form(model, kind, True)
        for label, wav in bench.timing_files():
            secs = wav_seconds(wav)
            t0 = time.perf_counter()
            nemo_transcribe(model, kind, [str(wav)], "ro", batch=1)
            took = time.perf_counter() - t0
            result[label] = {"audio_s": round(secs, 1), "seconds": round(took, 1), "rtfx": round(secs / took, 1)}
            bench.save(f"result_{kind}.json", result)
    bench.save(f"result_{kind}.json", result)
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def wav_seconds(path: Path) -> float:
    import soundfile as sf

    return sf.info(str(path)).duration


def whisper_child(bench: Bench) -> None:
    """Current pipeline's ASR (Whisper large-v3, ro+ru decodes). Own process: asr_llm switches HF offline.

    Weights come from asr_llm's usual place (MOM_ASR_MODEL_DIR, default models/whisper).
    """
    sys.path.insert(0, str(ASR_ROOT))
    import numpy as np

    from asr_llm.asr import WhisperAsr
    from asr_llm.audio import decode_audio
    from asr_llm.pipeline import transcribe_audio

    sets = json.loads(bench.sets_file.read_text())
    engine, result = WhisperAsr(), {"sets": {}}
    for name, items in sets.items():
        t0 = time.perf_counter()
        if name == "gold":
            transcript, _ = transcribe_audio(Path(items[0]["audio"]))
            hyps = [" ".join(s.text for s in transcript.segments)]
        else:
            hyps = [engine.transcribe_batch(decode_audio(Path(i["audio"])).astype(np.float32))[0] for i in items]
        result["sets"][name] = {**score([i["text"] for i in items], hyps), "seconds": round(time.perf_counter() - t0, 1)}
        bench.save("result_whisper.json", result)


def guarded(bench: Bench, name: str, fn, *args, **kwargs) -> None:
    """One model failing must not cost the others; the traceback is kept next to the results."""
    try:
        fn(*args, **kwargs)
    except Exception:
        (bench.out / f"{name}.error.txt").write_text(traceback.format_exc())
        traceback.print_exc()


# ---------------------------------------------------------------- main

def parse_model_paths(values: list[str]) -> dict[str, str]:
    paths = {}
    for value in values:
        kind, sep, path = value.partition("=")
        if not sep or (kind not in NEMO_MODELS and kind != "jackrabbit"):
            raise argparse.ArgumentTypeError(f"--model-path wants <parakeet|canary|jackrabbit>=<file.nemo>, got {value!r}")
        paths[kind] = path
    return paths


def split_list(value: str, allowed, what: str) -> list[str]:
    items = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in items if v not in allowed]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown {what}: {', '.join(unknown)}")
    return items


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--work", type=Path, default=Path("runs/zeroshot"))
    p.add_argument("--audio", type=Path, default=None, help="The meeting recording the gold belongs to.")
    p.add_argument("--gold", type=Path, default=GOLD)
    p.add_argument("--gold-seconds", type=float, default=181.0, help="Length of audio the gold covers.")
    p.add_argument("--n", type=int, default=int(os.environ.get("BENCH_N", "200")), help="Utterances per public test set.")
    p.add_argument("--sets", type=lambda v: split_list(v, MATRIX, "sets"), default=list(MATRIX))
    p.add_argument("--models", type=lambda v: split_list(v, MODELS, "models"), default=list(MODELS))
    p.add_argument("--model-path", action="append", default=[], help="kind=file.nemo: local weights instead of the Hub.")
    p.add_argument("--hf-mirror", type=Path, default=None, help="Local copies of the Hub repos; see asr_train/hub.py.")
    p.add_argument("--device", default="auto", help="auto | cuda:0 | cpu.")
    p.add_argument("--rebuild-sets", action="store_true")
    p.add_argument("--whisper-child", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    try:
        args.model_path = parse_model_paths(args.model_path)
    except argparse.ArgumentTypeError as exc:
        p.error(str(exc))
    if args.audio and not args.audio.exists():
        p.error(f"--audio {args.audio} does not exist")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    bench = Bench(args.work.expanduser().resolve())
    if args.whisper_child:
        whisper_child(bench)
        return
    hub = Hub(mirror=args.hf_mirror)
    if bench.sets_file.exists() and not args.rebuild_sets:
        sets = json.loads(bench.sets_file.read_text())
        print("reusing", bench.sets_file, {k: len(v) for k, v in sets.items()}, flush=True)
        if missing := [k for k in args.sets if k not in sets]:
            print(f"!! not in the reused sets: {', '.join(missing)} (--rebuild-sets to add them)", flush=True)
    else:
        sets = build_sets(bench, hub, args.n, args.sets, args.audio, args.gold, args.gold_seconds)
    sets = {k: v for k, v in sets.items() if k in args.sets}

    device = args.device
    if device == "auto" and any(m != "whisper" for m in args.models):
        import torch

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    for kind in args.models:
        if kind == "whisper":
            cmd = [sys.executable, "-m", "asr_train.zeroshot", "--work", str(bench.work), "--whisper-child"]
            guarded(bench, "whisper", sh, cmd, cwd=ASR_ROOT)
        else:
            guarded(bench, kind, run_nemo, bench, hub, kind, sets, args.model_path.get(kind), device)


if __name__ == "__main__":
    main()
