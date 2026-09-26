"""Run candidate models through extraction and writing on the eval meetings
and score them. Runs anywhere an Ollama server listens on 127.0.0.1; the
team runs it on Kaggle (eval/kaggle/kernel.py), never on a laptop.

  python -m eval.bakeoff --models gemma3:4b,qwen3:8b|think --out results/ [--long]
"""

import argparse
import json
import re
import subprocess
import threading
import time
from pathlib import Path

from eval.long import LONG
from eval.long import build as build_long
from eval.meetings import DATE, MEETINGS, build
from eval.score import score_meeting, summary
from mom.extract import extract
from mom.llm import LocalLLM
from mom.normalize import load_transcript
from mom.verify import verify
from mom.write import write_body

HERE = Path(__file__).resolve().parent
WRITE_ON = ("med01", "adm01")


class PeakGPU(threading.Thread):
    """Highest GPU memory in use while a model runs (GB, summed over GPUs)."""
    def __init__(self):
        super().__init__(daemon=True)
        self.peak, self.running = 0.0, True

    def run(self):
        while self.running:
            r = subprocess.run("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits",
                               shell=True, capture_output=True, text=True)
            try:
                self.peak = max(self.peak, sum(int(x) for x in r.stdout.split()) / 1024)
            except ValueError:
                pass
            time.sleep(2)


def language_tool():
    try:
        import language_tool_python
        return {lang: language_tool_python.LanguageTool(code) for lang, code in (("ro", "ro-RO"), ("ru", "ru-RU"), ("en", "en-GB"))}
    except Exception as e:  # Java or the package missing: fluency falls back to the script checks
        print(f"LanguageTool not available ({e!r}); skipping grammar counts", flush=True)
        return None


def plain_text(body: str) -> str:
    return re.sub(r"\\[a-z]+|\{[TNDAC]\d+\}|[{}]", " ", body)


def run_model(spec: str, data: Path, out: Path, tools=None, cpu_only=False, progress=None, only=None, with_long=False) -> dict:
    model, _, think = spec.partition("|")
    think_arg = {"think": True, "off": False, "low": "low", "medium": "medium"}.get(think) if think else None
    llm = LocalLLM(model, "http://127.0.0.1:11434", ctx=16384)
    if cpu_only:
        llm.cpu_only = True
    rows, written, t0 = [], {}, time.perf_counter()
    gpu = PeakGPU()
    gpu.start()
    ids = [m for m in {**MEETINGS, **LONG} if m in only] if only else list(MEETINGS) + (list(LONG) if with_long else [])
    for i, mid in enumerate(ids):
        lines = load_transcript(data / f"{mid}.txt")
        gold = json.loads((data / f"{mid}.gold.json").read_text(encoding="utf-8"))
        t = time.perf_counter()
        try:
            proposed, patients = extract(llm, lines, gold["type"], think=think_arg)
            ok_json = True
        except Exception as e:
            print(f"  {mid}: extraction failed: {e!r}", flush=True)
            proposed, patients, ok_json = [], [], False
        facts = verify(proposed, lines, DATE, [l.speaker for l in lines])
        s = score_meeting(facts, gold)
        s["json_ok"], s["extract_s"] = int(ok_json), round(time.perf_counter() - t, 1)
        rows.append(s)
        if mid in WRITE_ON and ok_json and not cpu_only:
            by_id = {l.id: l for l in lines}
            evidence = {f.id: " ".join(by_id[x].text for x in f.evidence if x in by_id) for f in facts}
            for lang in ("ro", "ru", "en"):
                t = time.perf_counter()
                body, rep = write_body(llm, facts, lang, evidence, patients, [l.speaker for l in lines])
                text = plain_text(body)
                lt = len(tools[lang].check(text)) if tools else None
                words = max(1, len(text.split()))
                leaked = [p for p in gold["patients"] if p.split()[-1] in body]
                written[f"{mid}_{lang}"] = {"body": body, "source": rep["source"], "errors": rep["errors"],
                                             "lt_errors_per_100": None if lt is None else round(100 * lt / words, 2),
                                             "patient_leaks": leaked, "write_s": round(time.perf_counter() - t, 1)}
        if progress:
            progress(i + 1, len(ids))
    gpu.running = False
    st = llm.stats
    result = {"model": spec, "cpu_only": cpu_only, "score": summary(rows), "per_meeting": rows,
              "writing": {k: {kk: vv for kk, vv in v.items() if kk != "body"} for k, v in written.items()},
              "tokens_per_s": round(st["output_tokens"] / st["seconds"], 1) if st["seconds"] else None,
              "prompt_tokens": st["prompt_tokens"], "output_tokens": st["output_tokens"],
              "minutes": round((time.perf_counter() - t0) / 60, 1), "peak_gpu_gb": round(gpu.peak, 1)}
    tag = spec.replace(":", "_").replace("/", "_").replace("|", "_") + ("_cpu" if cpu_only else "")
    (out / f"{tag}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{tag}.bodies.json").write_text(json.dumps({k: v["body"] for k, v in written.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--long", action="store_true", help="also run the one-hour meeting (eval/long.py)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    build(HERE / "data")
    build_long(HERE / "data")
    tools = language_tool()
    for spec in a.models.split(","):
        r = run_model(spec, HERE / "data", out, tools, with_long=a.long)
        print(json.dumps({"model": spec, **r["score"], "tok_s": r["tokens_per_s"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
