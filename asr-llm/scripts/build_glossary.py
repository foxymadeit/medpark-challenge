#!/usr/bin/env python3
"""One-time build of the RO/RU/EN medical dictionary. Never imported at runtime.

    python scripts/build_glossary.py wikidata    # local, needs internet: human labels for medical entities
    python scripts/build_glossary.py translate   # Kaggle GPU (vLLM): the rest + definitions, back-translated
    python scripts/build_glossary.py merge       # local: write data/medical_ro_ru_en.json

Sources: harvard_medical_dictionary.json (repo root, 2,050 EN terms + definitions)
and data/icu_terms_en.txt (ICU/cardiology terms). Only public terminology goes
out; no hospital data is involved.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ASR = Path(__file__).resolve().parents[1]
HARVARD = ASR.parent / "harvard_medical_dictionary.json"
ICU = ASR / "data" / "icu_terms_en.txt"
BUILD = ASR / "data" / "glossary_build"
WIKIDATA = BUILD / "wikidata.json"
TRANSLATED = BUILD / "translated.json"
GLOSSARY = ASR / "data" / "medical_ro_ru_en.json"

# Has a MeSH, UMLS or ICD-10 id: a medical entity, not the architectural "atrium".
MEDICAL = "wdt:P486|wdt:P2892|wdt:P494"


def load_terms() -> list[dict]:
    rows = [
        {"en": r["term"].strip(), "def_en": r["definition"].strip(), "source": "harvard"}
        for letter in json.loads(HARVARD.read_text(encoding="utf-8")).values()
        for r in letter
    ]
    for line in ICU.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            rows.append({"en": line.strip(), "def_en": "", "source": "icu"})
    seen, out = set(), []
    for r in rows:
        if r["en"].casefold() not in seen:
            seen.add(r["en"].casefold())
            out.append(r)
    return out


def _sparql(labels: list[str]) -> list[dict]:
    values = " ".join(json.dumps(v) + "@en" for v in labels)
    query = f"""SELECT ?lab ?item ?ro ?ru WHERE {{
      VALUES ?lab {{ {values} }}
      ?item rdfs:label|skos:altLabel ?lab ; {MEDICAL} [] .
      OPTIONAL {{ ?item rdfs:label ?ro FILTER(LANG(?ro) = "ro") }}
      OPTIONAL {{ ?item rdfs:label ?ru FILTER(LANG(?ru) = "ru") }}
    }}"""
    req = Request(
        "https://query.wikidata.org/sparql?" + urlencode({"query": query, "format": "json"}),
        headers={"User-Agent": "medpark-glossary-build/0.1 (hackathon; one-time dev build)"},
    )
    with urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())["results"]["bindings"]


def stage_wikidata() -> None:
    terms = load_terms()
    found: dict[str, dict] = json.loads(WIKIDATA.read_text()) if WIKIDATA.exists() else {}
    todo = [t["en"] for t in terms if t["en"].casefold() not in found]
    for k in range(0, len(todo), 60):
        batch = todo[k : k + 60]
        labels = sorted({v for t in batch for v in (t, t.lower())})
        for row in _sparql(labels):
            key = row["lab"]["value"].casefold()
            hit = found.setdefault(key, {"qid": row["item"]["value"].rsplit("/", 1)[-1]})
            for lang in ("ro", "ru"):
                if lang in row and lang not in hit:
                    hit[lang] = row[lang]["value"]
        BUILD.mkdir(parents=True, exist_ok=True)
        WIKIDATA.write_text(json.dumps(found, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print(f"{k + len(batch)}/{len(todo)} looked up, {len(found)} medical hits", flush=True)
        time.sleep(1.0)


SYSTEM = """You are a professional medical translator for hospitals in the Republic of Moldova.
Translate English medical terminology into Romanian (the clinical term doctors in Moldova and Romania use, with diacritics ă â î ș ț)
and Russian (standard Russian clinical terminology). Prefer the established clinical term over a literal translation.
If "known" translations are given, keep them unless they are wrong for the medical sense.
Return ONLY JSON: {"ro": string, "ru": string, "def_ro": string, "def_ru": string}"""

BACK = """Translate each medical term into English. Return ONLY JSON: {"from_ro": string, "from_ru": string}"""


def _json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        return {}


def close_enough(a: str, b: str) -> bool:
    fold = lambda s: re.sub(r"[^\w ]", "", s.casefold()).strip()  # noqa: E731
    return difflib.SequenceMatcher(None, fold(a), fold(b)).ratio() >= 0.75


def stage_translate(model: str, tp: int) -> None:
    from vllm import LLM, SamplingParams

    wiki = json.loads(WIKIDATA.read_text(encoding="utf-8"))
    terms = load_terms()
    llm = LLM(model=model, tensor_parallel_size=tp, dtype="float16", max_model_len=4096, gpu_memory_utilization=0.9)
    params = SamplingParams(temperature=0.0, max_tokens=700)

    tokenizer = llm.get_tokenizer()

    def chat(system: str, users: list[str]) -> list[dict]:
        prompts = [
            tokenizer.apply_chat_template(
                [{"role": "system", "content": system}, {"role": "user", "content": u}],
                tokenize=False,
                add_generation_prompt=True,
            )
            for u in users
        ]
        return [_json(o.outputs[0].text) for o in llm.generate(prompts, params)]

    asks = []
    for t in terms:
        known = {k: v for k, v in wiki.get(t["en"].casefold(), {}).items() if k in ("ro", "ru")}
        asks.append(json.dumps({"term": t["en"], "definition": t["def_en"], "known": known}, ensure_ascii=False))
    out = chat(SYSTEM, asks)
    backs = chat(BACK, [json.dumps({"ro": o.get("ro", ""), "ru": o.get("ru", "")}, ensure_ascii=False) for o in out])
    rows = []
    for t, o, b in zip(terms, out, backs):
        wiki_hit = wiki.get(t["en"].casefold(), {})
        rows.append(
            {
                **t,
                "ro": o.get("ro", ""),
                "ru": o.get("ru", ""),
                "def_ro": o.get("def_ro", ""),
                "def_ru": o.get("def_ru", ""),
                "wikidata": wiki_hit.get("qid"),
                "back_ok": close_enough(b.get("from_ro", ""), t["en"]) and close_enough(b.get("from_ru", ""), t["en"]),
            }
        )
    BUILD.mkdir(parents=True, exist_ok=True)
    TRANSLATED.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"translated {len(rows)}; back-translation ok {sum(r['back_ok'] for r in rows)}")


def stage_merge() -> None:
    glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    keep = [r for r in glossary["aligned"] if r.get("source") not in ("harvard", "icu")]
    have = {r["en"].casefold() for r in keep}
    added = []
    # Wikidata's human labels first; then the machine translation, only where back-translation agreed.
    wiki = json.loads(WIKIDATA.read_text(encoding="utf-8"))
    translated = {r["en"].casefold(): r for r in json.loads(TRANSLATED.read_text(encoding="utf-8"))} if TRANSLATED.exists() else {}
    rows = []
    for t in load_terms():
        w = wiki.get(t["en"].casefold()) or wiki.get(t["en"]) or {}
        m = translated.get(t["en"].casefold(), {})
        if w.get("ro") and w.get("ru"):
            rows.append({**t, "ro": w["ro"], "ru": w["ru"], "def_ro": m.get("def_ro", ""), "def_ru": m.get("def_ru", ""),
                         "wikidata": w["qid"], "back_ok": True, "labels": "wikidata"})
        elif m.get("back_ok") and m.get("ro") and m.get("ru"):
            rows.append({**m, "labels": "llm, back-translation checked"})
    for r in rows:
        if r["en"].casefold() not in have:
            have.add(r["en"].casefold())
            added.append({k: r.get(k, "") for k in ("source", "en", "ro", "ru", "def_en", "def_ro", "def_ru", "wikidata", "back_ok", "labels")})
    glossary["aligned"] = keep + added
    # Terms still without RO/RU stay English-only; retrieval and scoring read them from here.
    glossary["english_extra"] = sorted({t["en"] for t in load_terms() if t["en"].casefold() not in have}, key=str.casefold)
    glossary["meta"]["harvard_icu"] = (
        "Harvard Health dictionary + ICU list. RO/RU from Wikidata labels where a medical entity exists, "
        "else machine translation checked by back-translation (back_ok). Spot-check before relying on it."
    )
    GLOSSARY.write_text(json.dumps(glossary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"aligned rows: {len(glossary['aligned'])} (+{len(added)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=["wikidata", "translate", "merge"])
    parser.add_argument("--model", default="Qwen/Qwen2.5-32B-Instruct-AWQ")
    parser.add_argument("--tp", type=int, default=2, help="GPUs for vLLM tensor parallel (Kaggle T4 x2 = 2)")
    args = parser.parse_args()
    {"wikidata": stage_wikidata, "merge": stage_merge}.get(args.stage, lambda: stage_translate(args.model, args.tp))()
    sys.exit(0)
