"""Bake-off output -> one table and the default it implies.

    kaggle kernels output coflaz/liminal-asr-bakeoff -p runs/asr-bakeoff
    python scripts/kaggle_asr_bakeoff/summarize.py runs/asr-bakeoff

Rule for the default: among setups that transcribe an hour in at most BUDGET_S on the T4, the lowest
CER on the hand-corrected gold, provided it inserts no more words than the current pipeline
(whisper large-v3); LLM correction ships only if it lowers CER without adding insertions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BUDGET_S = 360.0
BASELINE = "whisper-large-v3"


def fold(text: str) -> str:
    import re

    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").casefold())).strip()


def insertions(ref: str, hyp: str) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from specialists import ops

    return ops(fold(ref).split(), fold(hyp).split())["ins"]


def main(root: Path) -> None:
    out = next(root.rglob("report.json")).parent
    rows: dict[str, dict] = {}
    for f in out.glob("result_whisper-*.json"):
        name = f.stem.removeprefix("result_")
        r = json.loads(f.read_text())
        gold = r["sets"].get("gold", {})
        hyp = next(iter(json.loads(p.read_text()) for p in out.glob(f"hyp_{name}_gold.json")), [{}])[0]
        hour = out / f"result_hour-{name.removeprefix('whisper-')}.json"
        rows[name] = {"gold_cer": gold.get("cer"), "gold_wer": gold.get("wer"),
                      "ins": insertions(hyp.get("ref", ""), hyp.get("hyp", "")) if hyp else None,
                      **{k: r["sets"].get(k, {}).get("wer") for k in ("fleurs_ro", "fleurs_ru", "fleurs_en", "cs_ru_en", "cs_ro_en", "rompar_md")},
                      "hour_s": json.loads(hour.read_text())["seconds"] if hour.exists() else None}
    spec = out / "result_specialists.json"
    if spec.exists():
        for name, r in json.loads(spec.read_text())["configs"].items():
            g = r.get("gold", {})
            rows[name] = {"gold_cer": g.get("cer"), "gold_wer": g.get("wer"), "ins": g.get("word_ins"),
                          "cer_ro_part": g.get("cer_ro_part"), "cer_ru_part": g.get("cer_ru_part"),
                          "script_mismatch": g.get("script_mismatch"), "terms": f"{g.get('terms_hit')}/{g.get('terms_in_gold')}",
                          **{k: r.get(k, {}).get("wer") for k in ("fleurs_ro", "fleurs_ru", "fleurs_en", "cs_ru_en", "cs_ro_en", "rompar_md")},
                          "hour_s": r.get("hour_seconds")}
    ger = out / "result_ger.json"
    if ger.exists():
        for key, r in json.loads(ger.read_text())["sets"].items():
            if key.endswith("_gold"):
                a = r["after"]
                rows["ger:" + key.removesuffix("_gold")] = {"gold_cer": a.get("cer"), "gold_wer": a.get("wer"), "ins": a.get("word_ins"),
                                                            "cer_ro_part": a.get("cer_ro_part"), "cer_ru_part": a.get("cer_ru_part"),
                                                            "script_mismatch": a.get("script_mismatch"),
                                                            "terms": f"{a.get('terms_hit')}/{a.get('terms_in_gold')}",
                                                            "ger_changed": r["changed"], "ger_s_per_min": round(60 * r["seconds"] / max(r["audio_s"], 1), 1)}
    cols = ["gold_cer", "gold_wer", "cer_ro_part", "cer_ru_part", "ins", "script_mismatch", "terms",
            "fleurs_ro", "fleurs_ru", "fleurs_en", "cs_ro_en", "cs_ru_en", "rompar_md", "hour_s"]
    print("| config | " + " | ".join(cols) + " |")
    print("|" + "---|" * (len(cols) + 1))
    for name, r in sorted(rows.items(), key=lambda kv: (kv[1].get("gold_cer") is None, kv[1].get("gold_cer") or 9)):
        print(f"| {name} | " + " | ".join("" if r.get(c) is None else str(r.get(c)) for c in cols) + " |")
    base_ins = (rows.get(BASELINE) or {}).get("ins")
    ok = {n: r for n, r in rows.items() if r.get("gold_cer") is not None and not n.startswith("ger:")
          and (r.get("hour_s") is None or r["hour_s"] <= BUDGET_S)
          and (base_ins is None or r.get("ins") is None or r["ins"] <= base_ins)}
    best = min(ok, key=lambda n: ok[n]["gold_cer"]) if ok else None
    print(f"\nreport: {json.loads((out / 'report.json').read_text()).get('peak_gpu_gb')}")
    print(f"default by the rule: {best} ({ok[best] if best else ''})")
    for n, r in rows.items():
        if n.startswith("ger:") and best and r["gold_cer"] is not None:
            base = rows.get(n.removeprefix("ger:").replace("_", ":", 1).replace("_", "+"), {})
            print(f"{n}: CER {base.get('gold_cer')} -> {r['gold_cer']}, insertions {base.get('ins')} -> {r['ins']}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
