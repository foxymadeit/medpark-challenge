"""Language specialists for the ASR bake-off, one engine per process (their dependencies clash).

    python specialists.py cut      --work W            # asr_llm: VAD utterances of gold / synthetic / 60 min, plus public test items
    python specialists.py nemo     --work W --model sped|sped-ctc|sped-ctc-lm|parakeet
    python specialists.py gigaam   --work W            # GigaAM-v3 e2e RNNT (Russian)
    python specialists.py combine  --work W            # singles, ensembles, corrector on/off -> out/result_specialists.json
    python specialists.py ger      --work W --llm ollama:gemma3:12b   # LLM error correction of unclear utterances

Every engine writes hyps/<model>.json: {item id: {"text", "words": [[start, end, word], ...]}} plus seconds per group.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ASR = HERE.parents[2]  # asr-llm/
SPED = ("gabrielpirlo/Sped_ParakeetRomanian_110M_TDT-CTC", "SpeD-ParakeetRo_110M_TDT-CTC.nemo")
SPED_LM = ("gabrielpirlo/SpeD-Romanian_6gram", "SpeD-Ro_6gram-tokens-prune0135.bin")
# The team recording's answer key (minutes/eval/team_recording/script.md, "Medical terms to check").
KEY_TERMS = ["supradenivelare de segment ST", "infarct miocardic acut", "ecocardiografie", "fracția de ejecție",
             "troponina", "creatinina", "insuficiență renală", "coronarografie", "substanța de contrast", "варфарин",
             "МНО", "abord radial", "ventilație mecanică", "sepsis", "hemoculturi", "Klebsiella", "meropenem",
             "HME фильтры", "AVC ischemic", "JCI", "hand hygiene compliance"]


def key_terms(ref: str, hyp: str) -> dict:
    """Answer-key terms said (in the reference) and heard (in the transcript). A word matches on its stem,
    all but its last two letters (at least 3), so "ecocardiografia" counts for "ecocardiografie"."""
    from asr_llm.clean import _fold

    def has(text: set[str], term: str) -> bool:
        return all(any(w.startswith(t[: max(3, len(t) - 2)]) for w in text) for t in _fold(term).split())

    r, h = set(_fold(ref).split()), set(_fold(hyp).split())
    said = [t for t in KEY_TERMS if has(r, t)]
    heard = [t for t in said if has(h, t)]
    return {"key_terms_said": len(said), "key_terms_heard": len(heard), "key_terms_missed": [t for t in said if t not in heard]}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- cut

def cut(work: Path) -> None:
    import soundfile as sf

    sys.path.insert(0, str(ASR))
    from asr_llm.audio import decode_audio
    from asr_llm.batching import pack_batches
    from asr_llm.vad import speech_spans

    sets = {**load(work / "sets.json"), **load(work / "run_sets.json")}
    # Whole recordings, cut into the product's VAD utterances: the gold, every --clip (synthetic, team), an hour.
    recordings = {"gold": sets["gold"][0], **{k: v[0] for k, v in sets.items() if k.startswith("clip_")},
                  "hour": {"audio": str(work / "data" / "medpark_60min.wav"), "text": None}}
    index: dict[str, list[dict]] = {}
    for name, rec in recordings.items():
        audio = decode_audio(Path(rec["audio"]))
        spans = speech_spans(audio)
        items = []
        for i, b in enumerate(pack_batches(audio, spans)):
            path = work / "utt" / name / f"{i:05d}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(path, b.samples, 16000)
            items.append({"id": f"{name}/{i:05d}", "audio": str(path), "start": b.start, "end": b.end})
        index[name] = items
        print(name, len(items), "utterances", flush=True)
    for name, rows in sets.items():
        if name not in recordings and not name.startswith("clip_"):
            index[name] = [{"id": f"{name}/{i:05d}", "audio": r["audio"], "text": r["text"]} for i, r in enumerate(rows)]
    save(work / "utt" / "index.json", {"index": index, "refs": {k: v["text"] for k, v in recordings.items()}})


def _items(work: Path) -> dict[str, list[dict]]:
    return load(work / "utt" / "index.json")["index"]


def _spread(text: str, start: float, end: float) -> list[list]:
    """Evenly spaced word times, for an engine that gives none."""
    words = text.split()
    step = (end - start) / max(len(words), 1)
    return [[round(start + k * step, 2), round(start + (k + 1) * step, 2), w] for k, w in enumerate(words)]


# ---------------------------------------------------------------- NeMo engines

def nemo(work: Path, model_name: str) -> None:
    import torch
    from huggingface_hub import hf_hub_download
    from nemo.collections.asr.models import ASRModel

    if model_name.startswith("sped"):
        model = ASRModel.restore_from(hf_hub_download(*SPED))
    else:
        model = ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v3")
    model = model.to(torch.device("cuda:0" if torch.cuda.is_available() else "cpu")).eval()
    if model_name == "sped-ctc":
        model.change_decoding_strategy(decoder_type="ctc")
    if model_name == "sped-ctc-lm":  # the authors' settings: beam 32, alpha 0.9, beta 2, token 6-gram
        from omegaconf import OmegaConf, open_dict

        cfg = OmegaConf.create(model.cfg.aux_ctc.decoding)
        with open_dict(cfg):
            cfg.strategy = "beam"
            cfg.beam.beam_size = 32
            cfg.beam.beam_alpha = 0.9
            cfg.beam.beam_beta = 2.0
            cfg.beam.search_type = "flashlight"
            cfg.beam.kenlm_path = hf_hub_download(*SPED_LM)
        model.change_decoding_strategy(decoding_cfg=cfg, decoder_type="ctc")
    out, seconds = {}, {}
    for group, items in _items(work).items():
        t0 = time.perf_counter()
        try:
            hyps = model.transcribe([i["audio"] for i in items], batch_size=16, timestamps=True)
        except Exception:  # some decoders give no timestamps
            hyps = model.transcribe([i["audio"] for i in items], batch_size=16)
        if isinstance(hyps, tuple):
            hyps = hyps[0]
        seconds[group] = round(time.perf_counter() - t0, 1)
        for it, h in zip(items, hyps):
            text = h.text if hasattr(h, "text") else str(h)
            base = it.get("start", 0.0)
            stamps = (getattr(h, "timestamp", None) or {}).get("word") or []
            words = [[round(base + w["start"], 2), round(base + w["end"], 2), w.get("word", "")] for w in stamps if "start" in w]
            out[it["id"]] = {"text": text, "words": words or _spread(text, base, it.get("end", base + 1.0))}
        print(model_name, group, len(items), seconds[group], "s", flush=True)
    save(work / "hyps" / f"{model_name}.json", {"hyps": out, "seconds": seconds})


# ---------------------------------------------------------------- GigaAM

def gigaam(work: Path) -> None:
    import gigaam as g

    model = g.load_model("v3_e2e_rnnt")
    out, seconds = {}, {}
    for group, items in _items(work).items():
        t0 = time.perf_counter()
        for it in items:
            base = it.get("start", 0.0)
            r = model.transcribe(it["audio"], word_timestamps=True)
            text = getattr(r, "text", None) or (r if isinstance(r, str) else "")
            ws = getattr(r, "words", None) or []
            words = [[round(base + w.start, 2), round(base + w.end, 2), w.text] for w in ws]
            out[it["id"]] = {"text": text, "words": words or _spread(text, base, it.get("end", base + 1.0))}
        seconds[group] = round(time.perf_counter() - t0, 1)
        print("gigaam", group, len(items), seconds[group], "s", flush=True)
    save(work / "hyps" / "gigaam.json", {"hyps": out, "seconds": seconds})


# ---------------------------------------------------------------- scoring helpers

def ops(ref: list, hyp: list) -> dict:
    """Substitutions, deletions and insertions of the best alignment."""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    s = de = ins = 0
    i, j = n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            s += ref[i - 1] != hyp[j - 1]
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            de, i = de + 1, i - 1
        else:
            ins, j = ins + 1, j - 1
    return {"sub": s, "del": de, "ins": ins}


def score_text(ref: str, hyp: str) -> dict:
    """CER/WER, insertions, CER on the Latin-only (RO/EN) and Cyrillic-only (RU) parts, answer-key terms."""
    from asr_llm.clean import _fold
    from asr_llm.score import error_rate

    r, h = _fold(ref), _fold(hyp)
    out = {"cer": round(error_rate(list(r), list(h)), 3), "wer": round(error_rate(r.split(), h.split()), 3)}
    out.update({f"word_{k}": v for k, v in ops(r.split(), h.split()).items()})
    for part, cyr in (("ro_part", False), ("ru_part", True)):
        pick = lambda t: " ".join(w for w in t.split() if any("Ѐ" <= c <= "ӿ" for c in w) == cyr)  # noqa: E731
        out[f"cer_{part}"] = round(error_rate(list(pick(r)), list(pick(h))), 3)
    return {**out, **key_terms(ref, hyp)}


def score_long(segments, ref: str) -> dict:
    """asr_llm's report (script mismatch, glossary term hits) plus score_text."""
    from asr_llm.score import report

    return {**report(segments, ref), **score_text(ref, " ".join(s.text for s in segments))}


def score_items(refs: list[str], hyps: list[str]) -> dict:
    from asr_train.metrics import fold, score

    out = score(refs, hyps)
    total = {"sub": 0, "del": 0, "ins": 0}
    for r, h in zip(refs, hyps):
        for k, v in ops(fold(r).split(), fold(h or "").split()).items():
            total[k] += v
    return {**out, **{f"word_{k}": v for k, v in total.items()}}


# ---------------------------------------------------------------- combine

def _segments(items, texts: dict[str, dict], langs: dict[str, str | None] | None = None):
    from asr_llm.schemas import SpeechSegment

    segs = []
    for it in items:
        t = texts.get(it["id"], {}).get("text", "")
        if t:
            segs.append(SpeechSegment(start=it["start"], end=it["end"], text=t,
                                      language=(langs or {}).get(it["id"]) or None))
    return segs


def combine(work: Path) -> None:
    sys.path.insert(0, str(ASR))
    from asr_llm.correct import correct_text
    from asr_llm.ensemble import Word, choose, combine as combine_one, language_of
    from asr_llm.schemas import Hypothesis, SpeechSegment

    meta = load(work / "utt" / "index.json")
    index, refs = meta["index"], meta["refs"]
    engines = {}
    for name in ("sped", "sped-ctc", "sped-ctc-lm", "gigaam", "parakeet"):
        f = work / "hyps" / f"{name}.json"
        if f.exists():
            engines[name] = load(f)
    result = {"engine_seconds": {k: v["seconds"] for k, v in engines.items()}, "configs": {}}

    def words_of(engine: str, item_id: str) -> list:
        return [Word(*w) for w in engines[engine]["hyps"].get(item_id, {}).get("words", [])]

    def ensemble(members: tuple[str, ...]) -> dict[str, dict]:
        out = {}
        for group, items in index.items():
            for it in items:
                hyps = {m: words_of(m, it["id"]) for m in members if m in engines}
                c = combine_one(hyps)
                c["hypotheses"] = {m: " ".join(w.text for w in ws) for m, ws in hyps.items()}
                c["fit"] = {m: round(choose({m: ws})[2], 3) for m, ws in hyps.items() if ws}
                out[it["id"]] = c
        return out

    configs: dict[str, dict[str, dict]] = {k: {i: {"text": v["text"]} for i, v in e["hyps"].items()} for k, e in engines.items()}
    members: dict[str, tuple[str, ...]] = {k: (k,) for k in engines}
    # The Romanian member: the SpeD decoding with the lowest mean CER on the gold and the team's code-switched
    # reading (weighted equally: the team recording is the closest thing to the judges' audio).
    ro_candidates = [k for k in ("sped", "sped-ctc", "sped-ctc-lm") if k in engines]
    if ro_candidates and "gigaam" in engines:
        decisive = [g for g in ("gold", "clip_team1") if refs.get(g)]
        gold_cer = {k: round(sum(score_long(_segments(index[g], configs[k]), refs[g])["cer"] for g in decisive) / len(decisive), 3)
                    for k in ro_candidates}
        ro_specialist = min(gold_cer, key=gold_cer.get)
        result["ro_specialist"] = {"chosen": ro_specialist, "gold_cer": gold_cer}
        for label, team in (("ensemble:ro+ru", (ro_specialist, "gigaam")), ("ensemble:ro+ru+multi", (ro_specialist, "gigaam", "parakeet"))):
            if all(m in engines for m in team):
                configs[label], members[label] = ensemble(team), team
    for name, texts in list(configs.items()):
        corrected = {}
        for item_id, v in texts.items():
            lang = v.get("language") or language_of([Word(0, 0, w) for w in v["text"].split()] or [Word(0, 0, "a")])
            corrected[item_id] = {**v, "text": correct_text(v["text"], lang.split("+")[0])[0]}
        configs[name + "+corrector"], members[name + "+corrector"] = corrected, members[name]

    for name, texts in configs.items():
        row = {}
        for group, items in index.items():
            if group in refs and not refs[group]:  # the hour (and any clip without a reference): timing only
                continue
            if group in refs:
                row[group] = score_long(_segments(items, texts, {i: v.get("language") for i, v in texts.items()}), refs[group])
            else:
                row[group] = score_items([i["text"] for i in items], [texts.get(i["id"], {}).get("text", "") for i in items])
        # Engines run one after another here; on the product server they would share one GPU the same way.
        row["hour_seconds"] = round(sum(engines[m]["seconds"].get("hour", 0.0) for m in members[name]), 1)
        row["members"] = list(members[name])
        result["configs"][name] = row
        print(name, {g: (r.get("cer"), r.get("wer")) for g, r in row.items() if isinstance(r, dict)}, flush=True)

    # Transcripts with every system's hypothesis, for the LLM error-correction step.
    for key in ("ensemble:ro+ru+multi", "ensemble:ro+ru"):
        if key not in configs:
            continue
        for group in [g for g, ref in refs.items() if ref]:
            segs = []
            for it in index[group]:
                c = configs[key].get(it["id"])
                if not c or not c["text"]:
                    continue
                hyps = [Hypothesis(language=language_of([Word(0, 0, w) for w in t.split()]), text=t, score=c["fit"].get(m), source=m)
                        for m, t in c["hypotheses"].items() if t]
                segs.append(SpeechSegment(start=it["start"], end=it["end"], text=c["text"],
                                          language=c["language"], hypotheses=hyps).model_dump())
            save(work / "ens" / f"{key.replace(':', '_').replace('+', '_')}__{group}.json", {"config": key, "group": group, "segments": segs})
        break
    save(work / "out" / "result_specialists.json", result)
    for group in [g for g, ref in refs.items() if ref]:
        save(work / "out" / f"specialist_texts_{group}.json", {k: [v.get(i["id"], {}).get("text", "") for i in index[group]] for k, v in configs.items()})


# ---------------------------------------------------------------- LLM error correction

def ger(work: Path, llm_spec: str) -> None:
    sys.path.insert(0, str(ASR))
    from asr_llm.fuse import fuse_single, is_unclear
    from asr_llm.config import settings
    from asr_llm.llm import make_llm
    from asr_llm.schemas import SpeechSegment

    refs = load(work / "utt" / "index.json")["refs"]
    llm = make_llm(llm_spec)
    result = {"llm": llm_spec, "margin": settings.fuse_margin, "floor": settings.fuse_floor, "sets": {}}
    for f in sorted((work / "ens").glob("*.json")):
        data = load(f)
        group = data["group"]
        segs = [SpeechSegment.model_validate(s) for s in data["segments"]]
        unclear = sum(is_unclear(s, settings.fuse_margin, settings.fuse_floor) for s in segs)
        t0 = time.perf_counter()
        fused = fuse_single(llm, segs)
        took = time.perf_counter() - t0
        result["sets"][f.stem] = {"config": data["config"], "group": group,
                                  "before": score_long(segs, refs[group]), "after": score_long(fused, refs[group]),
                                  "unclear": unclear, "changed": sum(a.text != b.text for a, b in zip(segs, fused)),
                                  "seconds": round(took, 1), "audio_s": round(segs[-1].end if segs else 0.0, 1)}
        print(f.stem, result["sets"][f.stem]["before"].get("cer"), "->", result["sets"][f.stem]["after"].get("cer"), flush=True)
    llm.close()
    save(work / "out" / "result_ger.json", result)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=["cut", "nemo", "gigaam", "combine", "ger"])
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--model", default="sped")
    p.add_argument("--llm", default="ollama:gemma3:12b")
    a = p.parse_args()
    sys.path.insert(0, str(ASR))
    {"cut": lambda: cut(a.work), "nemo": lambda: nemo(a.work, a.model), "gigaam": lambda: gigaam(a.work),
     "combine": lambda: combine(a.work), "ger": lambda: ger(a.work, a.llm)}[a.stage]()
