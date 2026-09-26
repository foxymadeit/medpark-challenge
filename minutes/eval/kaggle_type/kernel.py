"""Meeting-type detection, head to head: Laya (multilingual classifier) against
the local LLM Liminal already runs (qwen3:8b through Ollama), on CPU.

16 samples: the 7 scripted eval meetings and the team's mock board script,
each as the whole transcript and as its first 3 minutes. Writes
/kaggle/working/type_results.json with accuracy, per-sample answers and time.
"""
import json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

T0 = time.time()
OUT = Path("/kaggle/working")
def log(m): print(f"[{(time.time()-T0)/60:5.1f} min] {m}", flush=True)
def sh(c, **k): log("$ " + c); return subprocess.run(c, shell=True, check=True, **k)

sh("git clone -q --depth 1 -b Coflazo-Branch https://github.com/foxymadeit/medpark-challenge /tmp/repo")
sh(f"{sys.executable} -m pip install -q -e /tmp/repo/minutes 'laya[onnx]'")
sys.path.insert(0, "/tmp/repo/minutes")
from mom.normalize import load_transcript
from eval.meetings import build
from eval.long import build as build_long  # noqa: F401  (build() writes long01 too in this branch)

data = Path("/tmp/data"); build(data)
try:
    build_long(data)
except Exception as e:
    log(f"long01 build: {e!r}")
samples = []
for g in sorted(data.glob("*.gold.json")):
    gold = json.loads(g.read_text()); lines = load_transcript(g.with_suffix("").with_suffix(".txt"))
    full = "\n".join(f"{l.speaker}: {l.text}" for l in lines)
    early = "\n".join(f"{l.speaker}: {l.text}" for l in lines if l.start <= 180) or full
    samples += [(g.stem.replace(".gold", "") + ":full", gold["type"], full), (g.stem.replace(".gold", "") + ":3min", gold["type"], early)]
script = Path("/tmp/repo/minutes/eval/team_recording/script.md").read_text()
body = script.split("## Script", 1)[1].split("## Answer key", 1)[0]
team = "\n".join(t for _, t in re.findall(r"^\*\*(\w+):\*\*\s*(.+)$", body, re.M))
samples += [("team_script:full", "medical", team), ("team_script:3min", "medical", "\n".join(team.splitlines()[:14]))]
log(f"{len(samples)} samples")

CRITERIA = {"medical": "a medical board or clinical meeting: patients, diagnoses, treatments, wards, intensive care, surgery",
            "executive": "an executive or management meeting: strategy, budget, priorities, contracts, targets",
            "administrative": "an administrative meeting: rotas, staffing, procurement logistics, facilities, schedules, paperwork"}
results = {"samples": [s[0] for s in samples], "gold": [s[1] for s in samples]}

# --- with Laya
from laya import Router
t = time.time(); router = Router(); load_s = time.time() - t
q = {"meeting_type": {"type": "choice", "instructions": "What kind of hospital meeting is this transcript from?", "criteria": CRITERIA}}
laya = []
for name, gold, text in samples:
    t = time.time(); r = router.predict(text, q, model="multilingual", max_len=8192)
    laya.append({"answer": r["answers"]["meeting_type"]["choice"], "s": round(time.time() - t, 3)})
    log(f"laya {name}: {laya[-1]['answer']} (gold {gold})")
results["laya"] = {"answers": laya, "load_s": round(load_s, 1)}

# --- without Laya: the LLM Liminal already runs
sh("apt-get -qq update >/dev/null && apt-get -qq install -y zstd >/dev/null", )
sh("curl -fsSL https://ollama.com/install.sh | sh > /tmp/ollama-install.log 2>&1")
subprocess.Popen("OLLAMA_HOST=127.0.0.1:11434 ollama serve > /tmp/ollama.log 2>&1", shell=True)
time.sleep(8); sh("ollama pull qwen3:8b > /dev/null 2>&1")
from mom.llm import LocalLLM
llm = LocalLLM("qwen3:8b", "http://127.0.0.1:11434", ctx=16384); llm.cpu_only = True
schema = {"type": "object", "properties": {"meeting_type": {"type": "string", "enum": list(CRITERIA)}}, "required": ["meeting_type"]}
system = "You classify hospital meeting transcripts. Answer with the meeting type only.\n" + "\n".join(f"- {k}: {v}" for k, v in CRITERIA.items())
llm_ans = []
for name, gold, text in samples:
    t = time.time()
    try:
        a = llm.chat_json(system, "Transcript:\n" + text[:24000], schema, max_tokens=64)["meeting_type"]
    except Exception as e:
        a = f"error: {e!r}"[:80]
    llm_ans.append({"answer": a, "s": round(time.time() - t, 1)})
    log(f"llm {name}: {a} (gold {gold}) {llm_ans[-1]['s']}s")
results["llm_qwen3_8b_cpu"] = {"answers": llm_ans}

for key in ("laya", "llm_qwen3_8b_cpu"):
    ans = results[key]["answers"]; ok = sum(a["answer"] == g for a, g in zip(ans, results["gold"]))
    results[key]["accuracy"] = f"{ok}/{len(ans)}"; results[key]["mean_s"] = round(sum(a["s"] for a in ans) / len(ans), 2)
(OUT / "type_results.json").write_text(json.dumps(results, indent=1))
log("done: " + json.dumps({k: {x: results[k][x] for x in ("accuracy", "mean_s")} for k in ("laya", "llm_qwen3_8b_cpu")}))
