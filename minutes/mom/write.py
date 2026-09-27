"""Checked facts -> the LaTeX body in one language, written by the model and
checked by code.

Code prepares what must not drift (owners, deadlines, IDs), the model turns
the facts into minutes in the target language, and check_body enforces the
rules afterwards: only our commands, every fact ID exactly once, owners and
deadlines as given, no number or name the facts do not contain, no patient
names, no dashes. A body that still fails after one repair is replaced by a
plain one built from the facts, so a document always ships.
"""

import json
import os
import re
from pathlib import Path

from . import latexcheck
from .anonymize import anonymize_text
from .glossary import terms_for
from .schemas import format_date
from .verify import fold

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
LANGUAGE = {"ro": "Romanian (Republic of Moldova)", "ru": "Russian", "en": "English (British)"}
PARTICIPANT = {"ro": "Participantul", "ru": "Участник", "en": "Participant"}
_LABEL = re.compile(r"^(?:speaker|vorbitor(?:ul)?|participant(?:ul)?|участник|спикер|SPEAKER_?)\s*_?(\d+)$", re.I)
_NUM = re.compile(r"\d+(?:[.,]\d+)?")

EXAMPLE = {  # one small, impersonal example per language (see research/rules.md)
    "facts": [
        {"id": "S1", "kind": "summary", "text": ""},
        {"id": "T1", "kind": "topic", "text": "Contractul de mentenanță RMN"},
        {"id": "N1", "kind": "note", "topic": "T1", "text": "Contractul actual de mentenanță pentru RMN expiră la sfârșitul lunii."},
        {"id": "D1", "kind": "decision", "topic": "T1", "text": "Se începe reînnoirea contractului în această săptămână."},
        {"id": "A1", "kind": "action", "topic": "T1", "text": "Verifică condițiile de reînnoire.", "owner": "{P} 3", "deadline": "{DATE}"},
    ],
    "ro": r"""\summary{S1}{Consiliul a examinat contractul de mentenanță pentru aparatul RMN, care expiră la sfârșitul lunii, și a aprobat inițierea reînnoirii lui în această săptămână.}
\begin{agenda}
\agendaitem{T1}{Contractul de mentenanță pentru aparatul RMN}
\end{agenda}
\topic{T1}{Contractul de mentenanță pentru aparatul RMN}
\noted{N1}{S-a comunicat că actualul contract de mentenanță pentru aparatul RMN expiră la sfârșitul lunii.}
\decision{D1}{Se aprobă inițierea procedurii de reînnoire a contractului în această săptămână.}{}
\action{A1}{Participantul 3}{30.09.2026}{Verifică condițiile de reînnoire a contractului.}""",
    "ru": r"""\summary{S1}{Рассмотрен договор на техническое обслуживание аппарата МРТ, который истекает в конце месяца; принято решение начать его продление на этой неделе.}
\begin{agenda}
\agendaitem{T1}{Договор на техническое обслуживание аппарата МРТ}
\end{agenda}
\topic{T1}{Договор на техническое обслуживание аппарата МРТ}
\noted{N1}{Было сообщено, что действующий договор на обслуживание аппарата МРТ истекает в конце месяца.}
\decision{D1}{Начать процедуру продления договора на этой неделе.}{}
\action{A1}{Участник 3}{30.09.2026}{Проверить условия продления договора.}""",
    "en": r"""\summary{S1}{The Board considered the maintenance contract for the MRI scanner, which expires at the end of the month, and agreed to start its renewal this week.}
\begin{agenda}
\agendaitem{T1}{Maintenance contract for the MRI scanner}
\end{agenda}
\topic{T1}{Maintenance contract for the MRI scanner}
\noted{N1}{The Board was informed that the current maintenance contract for the MRI scanner expires at the end of the month.}
\decision{D1}{The Board agreed to start the renewal of the contract this week.}{}
\action{A1}{Participant 3}{30 September 2026}{Check the renewal terms of the contract.}""",
}


# capitalised pairs that are institutions or titles, not people
INSTITUTIONAL = {"the", "board", "boards", "consiliul", "consiliului", "medical", "medicala", "executive", "executiv",
                 "administrative", "administrativ", "ministry", "ministerul", "ministerului", "health", "sanatatii",
                 "participant", "participantul", "hospital", "spitalul", "committee", "comitetul", "procurement",
                 "icu", "ati", "mri", "rmn", "ct", "jci", "medpark", "liminal", "department", "sectia", "directorul"}
SAID_DEADLINE = {"ro": "termen spus", "ru": "срок со слов", "en": "deadline as said"}
SUMMARY = {
    "ro": "Ședința a examinat {t} subiecte: {titles}. S-au adoptat {d} hotărâri și s-au stabilit {a} acțiuni.",
    "ru": "Рассмотрено вопросов: {t} ({titles}). Принято решений: {d}, поручений: {a}.",
    "en": "The meeting considered {t} items: {titles}. It took {d} decisions and agreed {a} actions.",
}


def owner_display(owner: str, lang: str) -> str:
    m = _LABEL.match(owner.strip())
    return f"{PARTICIPANT[lang]} {m.group(1)}" if m else owner.strip()


MAX_NOTES = int(os.environ.get("MOM_MAX_NOTES", "4"))   # notes per topic in the written minutes


def _topics(facts) -> list:
    """The topics the minutes show: checked ones, and any with a checked item under it."""
    return [t for t in facts if t.kind == "topic" and (t.status == "ok" or t.status == "confirm" and any(
        f.topic == t.id and f.status == "ok" for f in facts))]


def unproven(facts) -> list:
    """Kept facts the minutes leave out: what the checks could not confirm, and
    anything outside the topics shown. facts.json and the app keep them for a person."""
    shown = {t.id for t in _topics(facts)}
    return [f for f in facts if f.status in ("ok", "confirm") and f.id not in shown
            and (f.status == "confirm" or f.kind != "topic" and f.topic not in shown)]


def plan(facts, lang: str) -> list:
    """The checked facts as the writer sees them, in document order, with owners
    and deadlines already written for this language. Unproven facts never reach
    the writer, so no document can carry them, not even in the summary."""
    kept = [f for f in facts if f.status == "ok"]
    topics = _topics(facts)
    out = []
    if topics:
        out.append({"id": "S1", "kind": "summary", "text": ""})
    for t in topics:
        out.append({"id": t.id, "kind": "topic", "text": t.text})
        for kind in ("note", "decision", "action"):
            rows = [x for x in kept if x.topic == t.id and x.kind == kind]
            if kind == "note":
                rows = rows[:MAX_NOTES]   # long meetings: the minutes stay readable; every note stays in facts.json
            for f in rows:
                row = {"id": f.id, "kind": kind, "topic": t.id, "text": f.text}
                if kind == "decision" and f.vote:
                    row["vote"] = f.vote
                if kind == "action":
                    row["owner"] = owner_display(f.owner, lang)
                    row["deadline"] = format_date(f.deadline, lang)
                    if f.deadline_phrase and not f.deadline:
                        row["text"] = f"{f.text} ({SAID_DEADLINE[lang]}: {f.deadline_phrase})"
                out.append(row)
    return out


def prompt(lang: str) -> str:
    example_facts = json.dumps(EXAMPLE["facts"], ensure_ascii=False).replace("{P}", PARTICIPANT[lang]).replace(
        "{DATE}", format_date("2026-09-30", lang))
    return ((PROMPTS / "write.md").read_text(encoding="utf-8")
            .replace("{LANGUAGE}", LANGUAGE[lang])
            .replace("{STYLE}", (PROMPTS / f"style_{lang}.md").read_text(encoding="utf-8").strip())
            .replace("{EXAMPLE_FACTS}", example_facts).replace("{EXAMPLE_BODY}", EXAMPLE[lang]))


def write_body(llm, facts, lang: str, evidence_text: dict, patients=(), names=()) -> tuple:
    """-> (body, report). evidence_text maps fact ID -> the text of its cited lines."""
    rows = plan(facts, lang)
    if not rows:
        return "", {"source": "empty", "errors": []}
    system = prompt(lang)
    user = "Facts:\n" + "\n".join(json.dumps({k: v for k, v in r.items() if k != "source"}, ensure_ascii=False) for r in rows)
    terms = [f"{t['matched']} → {t[lang]}" for t in terms_for([r["text"] for r in rows], lang) if fold(t["matched"]) != fold(t[lang])]
    if terms:
        user += "\n\nMedical terms to use (standard forms):\n" + "\n".join(terms)
    body = _strip_fences(llm.chat(system, user, max_tokens=3500, think=False))
    body, errors = check_body(body, rows, evidence_text, patients, names, lang)
    if errors:
        repair = user + "\n\nYour previous body broke these rules; write it again, fixing them:\n- " + "\n- ".join(errors[:12])
        body, errors2 = check_body(_strip_fences(llm.chat(system, repair, max_tokens=3500, think=False)),
                                   rows, evidence_text, patients, names, lang)
        if errors2:
            return fallback_body(rows, lang, patients), {"source": "fallback", "errors": errors2}
        return body, {"source": "model, repaired", "errors": errors}
    return body, {"source": "model", "errors": []}


def check_body(body: str, rows, evidence_text: dict, patients=(), names=(), lang="ro") -> tuple:
    try:
        blocks = latexcheck.parse(body)
    except latexcheck.BodyError as e:
        return body, [f"LaTeX: {e}"]
    errors = []
    expected = {r["id"]: r for r in rows}
    # a repeated block (same fact, same command) is dropped rather than failing the body
    kept, done = [], set()
    for b in blocks:
        key = (b.fact_id, b.kind)
        if b.kind == "needsconfirmation" or b.fact_id and key in done:   # unproven items are never printed
            continue
        done.add(key)
        kept.append(b)
    blocks = kept
    seen = {}
    for b in blocks:
        if b.fact_id:
            seen.setdefault(b.fact_id, []).append(b.kind)
    for fid, r in expected.items():
        want = {"summary": 1, "topic": 2, "note": 1, "decision": 1, "action": 1}[r["kind"]]
        got = len(seen.get(fid, []))
        if got != want:
            errors.append(f"{fid} appears {got} times; it must appear {want} time(s)")
    for fid in seen:
        if fid not in expected:
            errors.append(f"{fid} is not one of the given facts; remove it")

    everything = " ".join(f"{r.get('text', '')} {r.get('vote', '')} {r.get('deadline', '')}" for r in rows) + " " + " ".join(evidence_text.values())
    fixed = []
    # speaker names are not allowed in sentences: minutes are impersonal, names
    # belong to the attendance list and the owner column only
    for b in blocks:
        args = dict(b.args)
        r = expected.get(b.fact_id, {})
        if b.kind == "action" and r:
            args["owner"] = latexcheck.escape(anonymize_text(r.get("owner", ""), list(patients)))
            args["deadline"] = latexcheck.escape(r.get("deadline", ""))
        for key in ("text", "title", "vote"):
            if key not in args:
                continue
            text = anonymize_text(args[key], list(patients))
            text = text.replace(" — ", ", ").replace("—", ", ").replace(" – ", ", ")
            args[key] = text
            source = everything if b.kind == "summary" else (
                f"{r.get('text', '')} {r.get('vote', '')} {r.get('deadline', '')} " + evidence_text.get(b.fact_id, ""))
            plain = re.sub(r"\b(\d{1,2})[:.]00\b", r"\1", latexcheck.unescape(text))   # "10:00" is the 10 in "ora 10"
            for n in _NUM.findall(plain):
                if n.replace(",", ".") not in source.replace(",", "."):
                    errors.append(f"{b.fact_id}: the number {n} is not in the fact")
            for pair in re.findall(r"\b([A-Z][a-zăâîșț]+ [A-Z][a-zăâîșț]+)\b", text):
                if set(fold(pair).split()) & INSTITUTIONAL:
                    continue
                if not all(w in fold(source) for w in fold(pair).split()):
                    errors.append(f"{b.fact_id}: the name {pair!r} is not in the facts; minutes are impersonal")
            if lang in ("ro", "en") and re.search(r"[А-Яа-яЁё]{4,}", text):
                errors.append(f"{b.fact_id}: text contains Cyrillic; write it in {LANGUAGE[lang]}")
        fixed.append(latexcheck.Block(b.kind, args))
    return latexcheck.serialise(fixed), errors


def fallback_body(rows, lang: str = "en", patients=()) -> str:
    """Plain body from the facts themselves, used only if the model's body fails twice.
    Patients are anonymized here too, whatever the caller already did."""
    e = lambda t: latexcheck.escape(anonymize_text(t, list(patients)))  # noqa: E731
    count = lambda k: sum(r["kind"] == k for r in rows)  # noqa: E731
    titles = "; ".join(r["text"] for r in rows if r["kind"] == "topic")
    out = [f"\\summary{{S1}}{{{e(SUMMARY[lang].format(t=count('topic'), titles=titles, d=count('decision'), a=count('action')))}}}"] if count("topic") else []
    out += ["\\begin{agenda}"] + [f"\\agendaitem{{{r['id']}}}{{{e(r['text'])}}}" for r in rows if r["kind"] == "topic"] + ["\\end{agenda}"]
    for r in rows:
        k = r["kind"]
        if k == "topic":
            out.append(f"\\topic{{{r['id']}}}{{{e(r['text'])}}}")
        elif k == "note":
            out.append(f"\\noted{{{r['id']}}}{{{e(r['text'])}}}")
        elif k == "decision":
            out.append(f"\\decision{{{r['id']}}}{{{e(r['text'])}}}{{{e(r.get('vote', ''))}}}")
        elif k == "action":
            out.append(f"\\action{{{r['id']}}}{{{e(r['owner'])}}}{{{e(r['deadline'])}}}{{{e(r['text'])}}}")
    return "\n".join(out) + "\n"


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:latex|tex)?\s*", "", text)
    return re.sub(r"\s*```$", "", text).strip()
