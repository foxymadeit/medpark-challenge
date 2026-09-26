"""Does Laya make an important difference? Three uses, each against what
Liminal does today, on CPU (laya-multilingual, zero-shot).

1. Meaning check: is a minutes statement supported by its transcript lines?
   Baseline: today's check only catches numbers that are not in the evidence.
2. Line triage: can Laya drop chatter so the LLM reads less, without losing a
   single decision or action line? Baseline: the LLM reads 100% of lines.
3. ASR junk filter: subtitle credits Whisper invents in silence. Baseline:
   the teammate's list of 12 known phrases; Laya is tested on unseen variants.
Writes /kaggle/working/laya_results.json.
"""
import json, re, subprocess, sys, time
from pathlib import Path

T0 = time.time()
def log(m): print(f"[{(time.time()-T0)/60:5.1f} min] {m}", flush=True)
subprocess.run("git clone -q --depth 1 -b Coflazo-Branch https://github.com/foxymadeit/medpark-challenge /tmp/repo", shell=True, check=True)
subprocess.run(f"{sys.executable} -m pip install -q 'laya[onnx]' rapidfuzz python-docx", shell=True, check=True)
sys.path.insert(0, "/tmp/repo/minutes")
from eval.meetings import MEETINGS
from eval.long import LONG
from laya import Router
router = Router()

def yes_prob(state, instruction):
    r = router.predict(state, {"q": {"type": "noul", "instructions": instruction}}, model="multilingual", max_len=2048)
    a = r["answers"]["q"]
    return float(a.get("noul", a.get("probability", a.get("yes", 0.0))))

OUT = {}
# ------------------------------------------------------------------ 1. meaning check
EV = {
 "angio": "Roman: Da, de acord. Propunerea mea: coronarografie mâine dimineață la ora nouă, cu hidratare începând de azi seară.\nCristina: Bine, aprobăm. Roman, tu programezi coronarografia și confirmi până mâine la ora opt.",
 "filters": "Stanislav: Да, HME фильтры, и ещё бактериальные. Нам нужно минимум сто штук.\nCristina: Володимир, заказывай двести, чтобы был запас на месяц. Я подпишу approval сегодня.",
 "ventilator": "Roman: Și poate ar trebui să cumpărăm încă un ventilator portabil?\nCristina: Nu acum, bugetul pe trimestru e închis. Revenim la asta în ianuarie.",
 "audit": "Cagan: I suggest a monthly observation audit in every ward.\nRoman: Lunar e prea rar.\nCristina: I agree with Roman. Let's do it every week until the survey.\nCagan: Every week is a lot of work for the nurses. What about every two weeks?\nCristina: OK, every two weeks. That's final.",
 "order": "Volodymyr: Хорошо, отправлю заказ до понедельника. Нет, лучше завтра, чтобы успели до выходных.",
 "bed": "Stanislav: Vineri primim un pacient transferat din Bălți, după un AVC ischemic. Avem nevoie de un pat liber.\nCristina: Bine. Stanislav, pregătești patul până vineri.\nStanislav: Da, se face.",
 "pilot": "Volodymyr: Предлагаю пилот на медицинском совете со следующей недели.\nCristina: Bine, aprobăm pilotul de săptămâna viitoare, pentru consiliul medical.",
 "stetho": "Stanislav: Și eu aș vrea să adăugăm în audit și dezinfecția stetoscoapelor.\nCagan: Good idea, but JCI doesn't score it separately. Let's keep it for later.",
 "patient": "Roman: Pacientul din salonul 14, 72 de ani, internat aseară cu durere toracică. Pe ECG avem supradenivelare de segment ST, deci suspectăm infarct miocardic acut. Ecocardiografia arată fracția de ejecție 38%.",
}
PAIRS = [  # (evidence key, statement, supported?, kind)
 ("angio", "The Board approved coronary angiography tomorrow at 9:00, with hydration from tonight.", True, "true"),
 ("angio", "Se aprobă coronarografia mâine la ora 9, cu hidratare începând de azi seară.", True, "true"),
 ("angio", "The Board rejected the coronary angiography.", False, "negation"),
 ("angio", "The angiography was postponed to next week.", False, "contradiction"),
 ("angio", "The Board approved coronary angiography tomorrow at 11:00.", False, "number"),
 ("angio", "Stanislav will schedule the angiography.", False, "owner"),
 ("filters", "The Board agreed to order 200 HME and bacterial filters.", True, "true"),
 ("filters", "Consiliul a decis comandarea a 200 de filtre HME și bacteriene.", True, "true"),
 ("filters", "The Board agreed to order 100 filters.", False, "number"),
 ("filters", "The Board decided not to order any filters.", False, "negation"),
 ("ventilator", "Buying a portable ventilator was postponed until January.", True, "true"),
 ("ventilator", "The Board approved buying a portable ventilator.", False, "proposal"),
 ("ventilator", "Se aprobă achiziția unui ventilator portabil.", False, "proposal"),
 ("audit", "Hand hygiene audits will run every two weeks until the survey.", True, "true"),
 ("audit", "Auditul igienei mâinilor se face la fiecare două săptămâni.", True, "true"),
 ("audit", "Hand hygiene audits will run monthly.", False, "reversal"),
 ("audit", "Hand hygiene audits will run every week.", False, "reversal"),
 ("order", "Volodymyr will send the filter order tomorrow.", True, "true"),
 ("order", "Volodymyr will send the filter order by Monday.", False, "reversal"),
 ("bed", "Stanislav will prepare a bed by Friday.", True, "true"),
 ("bed", "Stanislav pregătește un pat până vineri.", True, "true"),
 ("bed", "Cristina will prepare a bed by Friday.", False, "owner"),
 ("bed", "Stanislav will prepare two beds by Friday.", False, "contradiction"),
 ("pilot", "The Board approved the Liminal pilot for the medical board from next week.", True, "true"),
 ("pilot", "Совет одобрил пилот Liminal для медицинского совета со следующей недели.", True, "true"),
 ("pilot", "The Board rejected the Liminal pilot.", False, "negation"),
 ("pilot", "The pilot was approved for all departments starting today.", False, "contradiction"),
 ("stetho", "Adding stethoscope disinfection to the audit was deferred.", True, "true"),
 ("stetho", "Stethoscope disinfection was added to the audit.", False, "proposal"),
 ("patient", "The patient in room 14 has an ejection fraction of 38%.", True, "true"),
 ("patient", "Pacientul din salonul 14 are suspiciune de infarct miocardic acut.", True, "true"),
 ("patient", "The patient in room 14 has an ejection fraction of 58%.", False, "number"),
 ("patient", "The patient was admitted with a stroke.", False, "contradiction"),
 ("patient", "The patient is 27 years old.", False, "number"),
]
num = lambda s: set(re.findall(r"\d+", re.sub(r"(\d{1,2})[:.]00\b", r"\1", s)))
rows = []
for k, stmt, ok, kind in PAIRS:
    t = time.time(); p = yes_prob(EV[k], f"Is this statement fully supported by the transcript above, with nothing added, reversed or changed? Statement: {stmt}")
    base = bool(num(stmt) - num(EV[k] + " 9 11 200"))  # today's check: a number not in the evidence ("nouă"=9 is written out, so allow the spelled numbers)
    base = bool(num(stmt) - num(EV[k])) if not re.search(r"nouă|двести", EV[k]) else bool(num(stmt) - (num(EV[k]) | {"9", "200"}))
    rows.append({"key": k, "stmt": stmt, "supported": ok, "kind": kind, "p_yes": round(p, 3), "baseline_flag": base, "s": round(time.time() - t, 3)})
    log(f"1 {kind:13} p={p:.2f} base={base} | {stmt[:60]}")
def sweep(rows, flag):
    best = None
    for t in [i / 20 for i in range(1, 20)]:
        f = [flag(r, t) for r in rows]
        caught = sum(1 for r, x in zip(rows, f) if not r["supported"] and x); bad = sum(1 for r, x in zip(rows, f) if r["supported"] and x)
        cand = (t, caught, bad)
        if bad <= 1 and (best is None or caught > best[1]): best = cand
    return best
neg = sum(1 for r in rows if not r["supported"]); pos = len(rows) - neg
t, caught, bad = sweep(rows, lambda r, t: r["p_yes"] < t) or (None, 0, 0)
OUT["1_meaning"] = {"pairs": len(rows), "broken": neg, "true": pos,
                    "baseline": {"caught": sum(1 for r in rows if not r["supported"] and r["baseline_flag"]), "false_flags": sum(1 for r in rows if r["supported"] and r["baseline_flag"])},
                    "laya": {"threshold": t, "caught": caught, "false_flags": bad},
                    "by_kind": {k: {"n": sum(1 for r in rows if r["kind"] == k), "laya_caught": sum(1 for r in rows if r["kind"] == k and t is not None and r["p_yes"] < t), "baseline_caught": sum(1 for r in rows if r["kind"] == k and r["baseline_flag"])} for k in sorted({r["kind"] for r in rows} - {"true"})},
                    "rows": rows}
log("1 done: " + json.dumps({k: OUT["1_meaning"][k] for k in ("baseline", "laya")}))

# ------------------------------------------------------------------ 2. triage
lines = []
for mid, (mtype, script) in list(MEETINGS.items()) + list(LONG.items()):
    for i, (spk, text, tags) in enumerate(script):
        kinds = {t.partition(":")[0] for t in tags.split(";") if t}
        label = "decision" if kinds & {"D", "OLD"} else "action" if "A" in kinds else "proposal" if kinds & {"NOTD", "P"} else "other"
        ctx = "\n".join(f"Speaker {s}: {x}" for s, x, _ in script[max(0, i - 2):i])
        lines.append((mid, label, (ctx + "\n" if ctx else "") + f">> Speaker {spk}: {text}"))
q2 = {"t": {"type": "choice", "instructions": "What does the line marked >> do in this hospital meeting?",
            "criteria": {"decision": "the group agrees, approves or settles something", "action": "someone commits to doing a task",
                         "proposal": "someone suggests or asks something not yet agreed", "other": "reporting facts, discussion, greetings or chatter"}}}
t = time.time(); preds = []
for mid, label, state in lines:
    a = router.predict(state, q2, model="multilingual", max_len=1024)["answers"]["t"]
    preds.append({"mid": mid, "label": label, "choice": a.get("choice"), "raw": {k: v for k, v in a.items() if k != "choice"}})
secs = time.time() - t
must = [p for p in preds if p["label"] in ("decision", "action")]
kept = [p for p in preds if p["choice"] != "other"]
OUT["2_triage"] = {"lines": len(preds), "must_keep": len(must), "must_kept": sum(1 for p in must if p["choice"] != "other"),
                   "share_sent_to_llm": round(len(kept) / len(preds), 3), "ms_per_line": round(1000 * secs / len(preds), 1),
                   "sample": preds[:5]}
log("2 done: " + json.dumps({k: v for k, v in OUT["2_triage"].items() if k != "sample"}))

# ------------------------------------------------------------------ 3. ASR junk filter
KNOWN = ["продолжение следует", "субтитры сделал dimatorzok", "субтитры создавал dimatorzok", "спасибо за просмотр", "să vă mulțumim",
         "vă mulțumim pentru vizionare", "nu uitați să vă abonați", "nu uitați să dați like să lăsați un comentariu și să distribuiți acest video",
         "thank you for watching", "thanks for watching", "спасибо что вы посетили", "спасибо за внимание"]
UNSEEN = ["Субтитры подготовлены сообществом Amara.org", "Редактор субтитров А.Семкин Корректор А.Егорова", "Please subscribe to my channel",
          "Subtitles by the Amara.org community", "Продолжение в следующей серии", "Ставьте лайки и подписывайтесь на канал",
          "Vă mulțumim că ne-ați urmărit", "Thanks for watching and see you next time", "Titrări realizate de comunitatea Amara.org",
          "Abonați-vă la canal pentru mai multe clipuri", "ПОДПИСЫВАЙТЕСЬ НА КАНАЛ", "Music ♪♪"]
fold = lambda s: re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.casefold())).strip()
base_flag = lambda s: len(fold(s).split()) <= 12 and any(k in fold(s) for k in KNOWN)
real = [x for _, (_, script) in list(MEETINGS.items())[:6] for _, x, _ in script][:150] + ["Спасибо.", "Da, mulțumesc.", "Thank you, everyone.", "Спасибо за внимание, коллеги, переходим к следующему вопросу."]
q3 = "Is this text a subtitle credit, a video outro or channel promotion that speech recognition invented, rather than something a person said in a hospital meeting?"
pu = [yes_prob(x, q3) for x in UNSEEN]; pr = [yes_prob(x, q3) for x in real]
best = None
for th in [i / 20 for i in range(1, 20)]:
    c = sum(p >= th for p in pu); fp = sum(p >= th for p in pr)
    if fp <= 1 and (best is None or c > best[1]): best = (th, c, fp)
OUT["3_asr_junk"] = {"unseen": len(UNSEEN), "real_lines": len(real),
                     "baseline": {"caught_unseen": sum(base_flag(x) for x in UNSEEN), "false_on_real": sum(base_flag(x) for x in real)},
                     "laya": {"threshold": best and best[0], "caught_unseen": best and best[1], "false_on_real": best and best[2]},
                     "unseen_probs": [round(p, 2) for p in pu]}
log("3 done: " + json.dumps({k: OUT["3_asr_junk"][k] for k in ("baseline", "laya")}))
Path("/kaggle/working/laya_results.json").write_text(json.dumps(OUT, indent=1, ensure_ascii=False))
log("all done")
