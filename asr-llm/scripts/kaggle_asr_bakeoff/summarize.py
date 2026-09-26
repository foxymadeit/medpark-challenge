"""Bake-off output -> one table per recording and the default it implies.

    kaggle kernels output coflaz/liminal-asr-bakeoff -p runs/asr-bakeoff
    python scripts/kaggle_asr_bakeoff/summarize.py runs/asr-bakeoff

Rule for the default: among setups that transcribe an hour in at most BUDGET_S on the T4, the lowest
mean CER over the hand-corrected gold and the team's code-switched reading (weighted equally: the
team recording is the closest thing to the judges' audio), provided it inserts no more words on those
two than the current pipeline (whisper large-v3). LLM correction ships only if it lowers that CER
without adding insertions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # asr-llm/, for asr_llm
sys.path.insert(0, str(Path(__file__).resolve().parent))
from specialists import score_text  # noqa: E402

BUDGET_S = 360.0
BASELINE = "whisper-large-v3"
GROUPS = ("gold", "clip_team1", "clip_team2", "clip_synthetic")
DECISIVE = ("gold", "clip_team1")
COLS = ("cer", "wer", "cer_ro_part", "cer_ru_part", "word_ins", "script_mismatch", "key_terms")


def main(root: Path) -> None:
    out = next(root.rglob("report.json")).parent
    rows: dict[str, dict] = {}  # config -> group -> scores, plus hour_s
    for group in GROUPS:  # engines scored by asr_train.zeroshot: whole-recording hypotheses
        for f in out.glob(f"hyp_*_{group}.json"):
            name = f.stem.removeprefix("hyp_").removesuffix(f"_{group}")
            pair = json.loads(f.read_text(encoding="utf-8"))[0]
            if pair.get("ref"):
                rows.setdefault(name, {})[group] = score_text(pair["ref"], pair.get("hyp") or "")
    for name in list(rows):
        hour = out / f"result_hour-{name.removeprefix('whisper-')}.json"
        if hour.exists():
            rows[name]["hour_s"] = json.loads(hour.read_text())["seconds"]
        res = out / f"result_{name}.json"
        if res.exists() and "medpark_60min" in json.loads(res.read_text()):
            rows[name]["hour_s"] = json.loads(res.read_text())["medpark_60min"]["seconds"]
    spec = out / "result_specialists.json"
    if spec.exists():
        for name, r in json.loads(spec.read_text())["configs"].items():
            rows[name] = {g: r[g] for g in GROUPS if g in r} | {"hour_s": r.get("hour_seconds")}
    ger = out / "result_ger.json"
    if ger.exists():
        for r in json.loads(ger.read_text())["sets"].values():
            rows.setdefault("ger:" + r["config"], {"hour_s": None})[r["group"]] = {**r["after"], "ger_changed": r["changed"]}

    def cell(s: dict, c: str) -> str:
        if c == "key_terms":
            return f"{s.get('key_terms_heard')}/{s.get('key_terms_said')}" if s.get("key_terms_said") else ""
        return "" if s.get(c) is None else str(s[c])

    for group in GROUPS:
        print(f"\n### {group}\n\n| config | " + " | ".join(COLS) + " | hour_s |\n|" + "---|" * (len(COLS) + 2))
        for name, r in sorted(rows.items(), key=lambda kv: kv[1].get(group, {}).get("cer", 9)):
            if group in r:
                print(f"| {name} | " + " | ".join(cell(r[group], c) for c in COLS) + f" | {r.get('hour_s') or ''} |")

    def mean(r: dict, key: str) -> float | None:
        vals = [r[g][key] for g in DECISIVE if g in r and r[g].get(key) is not None]
        return sum(vals) / len(vals) if len(vals) == len([g for g in DECISIVE if any(g in x for x in rows.values())]) else None

    base_ins = mean(rows.get(BASELINE, {}), "word_ins")
    ok = {n: r for n, r in rows.items() if mean(r, "cer") is not None and not n.startswith("ger:")
          and (r.get("hour_s") is None or r["hour_s"] <= BUDGET_S)
          and (base_ins is None or mean(r, "word_ins") is None or mean(r, "word_ins") <= base_ins)}
    ranked = sorted(ok, key=lambda n: mean(ok[n], "cer"))
    print(f"\npeak GPU GB: {json.loads((out / 'report.json').read_text()).get('peak_gpu_gb')}")
    print("ranking by mean CER over " + " + ".join(DECISIVE) + ":")
    for n in ranked[:8]:
        print(f"  {n}: {mean(ok[n], 'cer'):.3f} (insertions {mean(ok[n], 'word_ins')}, hour {ok[n].get('hour_s')} s)")
    for n, r in rows.items():
        if n.startswith("ger:"):
            base = rows.get(n.removeprefix("ger:"), {})
            print(f"{n}: mean CER {mean(base, 'cer')} -> {mean(r, 'cer')}, insertions {mean(base, 'word_ins')} -> {mean(r, 'word_ins')}")
    print(f"default by the rule: {ranked[0] if ranked else None}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
