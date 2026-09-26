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
import re
from pathlib import Path

from . import latexcheck
from .anonymize import anonymize_text
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
        {"id": "D1", "kind": "decision", "topic": "T1", "text": "Se începe reînnoirea contractului în această săptămână.", "vote": "pro 4, contra 0"},
        {"id": "A1", "kind": "action", "topic": "T1", "text": "Verifică condițiile de reînnoire.", "owner": "{P} 3", "deadline": "{DATE}"},
        {"id": "C1", "kind": "confirm", "text": "Cine trimite documentele la Minister (nu s-a spus)."},
    ],
    "ro": r"""\summary{S1}{Consiliul a examinat contractul de mentenanță pentru aparatul RMN, care expiră la sfârșitul lunii, și a aprobat inițierea reînnoirii lui în această săptămână.}
\begin{agenda}
\agendaitem{T1}{Contractul de mentenanță pentru aparatul RMN}
\end{agenda}
\topic{T1}{Contractul de mentenanță pentru aparatul RMN}
\noted{N1}{S-a comunicat că actualul contract de mentenanță pentru aparatul RMN expiră la sfârșitul lunii.}
\decision{D1}{Se aprobă inițierea procedurii de reînnoire a contractului în această săptămână.}{pro 4, contra 0}
\action{A1}{Participantul 3}{30.09.2026}{Verifică condițiile de reînnoire a contractului.}
\needsconfirmation{C1}{Persoana care transmite documentele la Minister nu a fost numită.}""",
    "ru": r"""\summary{S1}{Рассмотрен договор на техническое обслуживание аппарата МРТ, который истекает в конце месяца; принято решение начать его продление на этой неделе.}
\begin{agenda}
\agendaitem{T1}{Договор на техническое обслуживание аппарата МРТ}
\end{agenda}
\topic{T1}{Договор на техническое обслуживание аппарата МРТ}
\noted{N1}{Было сообщено, что действующий договор на обслуживание аппарата МРТ истекает в конце месяца.}
\decision{D1}{Начать процедуру продления договора на этой неделе.}{«за» - 4, «против» - 0}
\action{A1}{Участник 3}{30.09.2026}{Проверить условия продления договора.}
\needsconfirmation{C1}{Не названо, кто направляет документы в Министерство.}""",
    "en": r"""\summary{S1}{The Board considered the maintenance contract for the MRI scanner, which expires at the end of the month, and agreed to start its renewal this week.}
\begin{agenda}
\agendaitem{T1}{Maintenance contract for the MRI scanner}
\end{agenda}
\topic{T1}{Maintenance contract for the MRI scanner}
\noted{N1}{The Board was informed that the current maintenance contract for the MRI scanner expires at the end of the month.}
\decision{D1}{The Board agreed to start the renewal of the contract this week.}{4 for, 0 against}
\action{A1}{Participant 3}{30 September 2026}{Check the renewal terms of the contract.}
\needsconfirmation{C1}{No one was named to send the documents to the Ministry.}""",
}


SAID_DEADLINE = {"ro": "termen spus", "ru": "срок со слов", "en": "deadline as said"}
SUMMARY = {
    "ro": "Ședința a examinat {t} subiecte: {titles}. S-au adoptat {d} hotărâri și s-au stabilit {a} acțiuni.",
    "ru": "Рассмотрено вопросов: {t} ({titles}). Принято решений: {d}, поручений: {a}.",
    "en": "The meeting considered {t} items: {titles}. It took {d} decisions and agreed {a} actions.",
}


def owner_display(owner: str, lang: str) -> str:
    m = _LABEL.match(owner.strip())
    return f"{PARTICIPANT[lang]} {m.group(1)}" if m else owner.strip()


def plan(facts, lang: str) -> list:
    """The facts as the writer sees them, in document order, with owners and
    deadlines already written for this language and confirm items as C-IDs."""
    kept = [f for f in facts if f.status in ("ok", "confirm")]
    topics = [f for f in kept if f.kind == "topic"]
    out, n_confirm = [], 0
    if topics:
        out.append({"id": "S1", "kind": "summary", "text": ""})
    for t in topics:
        out.append({"id": t.id, "kind": "topic", "text": t.text})
        for kind in ("note", "decision", "action"):
            for f in (x for x in kept if x.topic == t.id and x.kind == kind and x.status == "ok"):
                row = {"id": f.id, "kind": kind, "topic": t.id, "text": f.text}
                if kind == "decision" and f.vote:
                    row["vote"] = f.vote
                if kind == "action":
                    row["owner"] = owner_display(f.owner, lang)
                    row["deadline"] = format_date(f.deadline, lang)
                    if f.deadline_phrase and not f.deadline:
                        row["text"] = f"{f.text} ({SAID_DEADLINE[lang]}: {f.deadline_phrase})"
                out.append(row)
    for f in kept:
        if f.status == "confirm" or (f.kind != "topic" and f.topic not in {t.id for t in topics}):
            n_confirm += 1
            out.append({"id": f"C{n_confirm}", "kind": "confirm", "text": f.text, "source": f.id})
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
    body = _strip_fences(llm.chat(system, user, max_tokens=3500, think=False))
    body, errors = check_body(body, rows, evidence_text, patients, names, lang)
    if errors:
        repair = user + "\n\nYour previous body broke these rules; write it again, fixing them:\n- " + "\n- ".join(errors[:12])
        body, errors2 = check_body(_strip_fences(llm.chat(system, repair, max_tokens=3500, think=False)),
                                   rows, evidence_text, patients, names, lang)
        if errors2:
            return fallback_body(rows, lang), {"source": "fallback", "errors": errors2}
        return body, {"source": "model, repaired", "errors": errors}
    return body, {"source": "model", "errors": []}


def check_body(body: str, rows, evidence_text: dict, patients=(), names=(), lang="ro") -> tuple:
    try:
        blocks = latexcheck.parse(body)
    except latexcheck.BodyError as e:
        return body, [f"LaTeX: {e}"]
    errors = []
    expected = {r["id"]: r for r in rows}
    seen = {}
    for b in blocks:
        if b.fact_id:
            seen.setdefault(b.fact_id, []).append(b.kind)
    for fid, r in expected.items():
        want = {"summary": 1, "topic": 2, "note": 1, "decision": 1, "action": 1, "confirm": 1}[r["kind"]]
        got = len(seen.get(fid, []))
        if got != want:
            errors.append(f"{fid} appears {got} times; it must appear {want} time(s)")
    for fid in seen:
        if fid not in expected:
            errors.append(f"{fid} is not one of the given facts; remove it")

    everything = " ".join(f"{r.get('text', '')} {r.get('vote', '')} {r.get('deadline', '')}" for r in rows) + " " + " ".join(evidence_text.values())
    fixed = []
    allowed_names = {w for n in names for w in fold(n).split()}
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
                f"{r.get('text', '')} {r.get('vote', '')} {r.get('deadline', '')} " + evidence_text.get(r.get("source", b.fact_id), ""))
            for n in _NUM.findall(latexcheck.unescape(text)):
                if n.replace(",", ".") not in source.replace(",", "."):
                    errors.append(f"{b.fact_id}: the number {n} is not in the fact")
            for pair in re.findall(r"\b([A-Z][a-zăâîșț]+ [A-Z][a-zăâîșț]+)\b", text):
                if not all(w in allowed_names or w in fold(source) for w in fold(pair).split()):
                    errors.append(f"{b.fact_id}: the name {pair!r} is not in the facts; minutes are impersonal")
            if lang in ("ro", "en") and re.search(r"[А-Яа-яЁё]{4,}", text):
                errors.append(f"{b.fact_id}: text contains Cyrillic; write it in {LANGUAGE[lang]}")
        fixed.append(latexcheck.Block(b.kind, args))
    return latexcheck.serialise(fixed), errors


def fallback_body(rows, lang: str = "en") -> str:
    """Plain body from the facts themselves, used only if the model's body fails twice."""
    e = latexcheck.escape
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
        elif k == "confirm":
            out.append(f"\\needsconfirmation{{{r['id']}}}{{{e(r['text'])}}}")
    return "\n".join(out) + "\n"


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:latex|tex)?\s*", "", text)
    return re.sub(r"\s*```$", "", text).strip()
