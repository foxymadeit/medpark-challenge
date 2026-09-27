"""Transcript in, minutes out: normalize, extract, verify, anonymize, write,
render. One function for the command line and for the web backend."""

import datetime as dt
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from . import latexcheck, render_docx, render_pdf
from .export import meeting_json
from .anonymize import anonymize_text
from .extract import extract
from .normalize import load_transcript
from .schemas import MEETING_TYPES, Meeting, fresh, to_dict
from .verify import report as verify_report
from .verify import verify
from .write import owner_display, write_body


def attendees(lines, lang: str, patients=()) -> list:
    """Speakers in order of first appearance, with talk time. No names are
    invented: an unnamed speaker is 'Participant N'."""
    talk, order = {}, []
    for l in lines:
        who = l.speaker or ""
        if not who:
            continue
        if who not in talk:
            order.append(who)
            talk[who] = 0.0
        talk[who] += max(0.0, l.end - l.start)
    unit = {"ro": "min", "ru": "мин", "en": "min"}[lang]
    return [{"name": anonymize_text(owner_display(w, lang), list(patients)), "role": f"{talk[w] / 60:.0f} {unit}" if talk[w] >= 30 else ""} for w in order]


def run(transcript, out_dir, llm, meeting: Meeting, langs=("ro", "ru", "en"), session=None, think=None) -> dict:
    if meeting.type not in MEETING_TYPES:
        raise ValueError(f"meeting type must be one of {', '.join(MEETING_TYPES)}")
    if meeting.date:
        dt.date.fromisoformat(meeting.date)   # the date becomes part of every file name
    t0 = time.perf_counter()
    timings = {}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)

    lines = load_transcript(transcript, session)
    if not lines:
        raise ValueError("the transcript has no text")
    timings["read"] = time.perf_counter() - t0
    if not meeting.date:
        meeting = replace(meeting, date=dt.date.today().isoformat())
    if meeting.start and not meeting.end:
        h, m = map(int, meeting.start.split(":"))
        end = dt.datetime(2000, 1, 1, h, m) + dt.timedelta(seconds=lines[-1].end)
        meeting = replace(meeting, end=end.strftime("%H:%M"))

    t = time.perf_counter()
    proposed, patients = extract(llm, lines, meeting.type, think=think)
    timings["extract"] = time.perf_counter() - t

    t = time.perf_counter()
    names = [l.speaker for l in lines if l.speaker] + [p["name"] for p in meeting.attendees]
    facts = verify(proposed, lines, meeting.date, names)
    facts = [replace(f, text=anonymize_text(f.text, patients), owner=anonymize_text(f.owner, patients)) for f in facts]
    by_id = {l.id: l for l in lines}
    evidence = {f.id: " ".join(by_id[i].text for i in f.evidence if i in by_id) for f in facts}
    timings["verify"] = time.perf_counter() - t
    counts = verify_report(facts)
    verified = f"{counts['ok']}/{counts['checked']}"

    bodies, write_reports = {}, {}
    t = time.perf_counter()
    for lang in langs:
        bodies[lang], write_reports[lang] = write_body(llm, facts, lang, evidence, patients, names)
    timings["write"] = time.perf_counter() - t

    t = time.perf_counter()
    stem = f"MoM_{meeting.date}_{meeting.type}"
    model = getattr(llm, "model", "local model")

    def render(lang):
        people = [{**p, "name": anonymize_text(p["name"], patients)} for p in meeting.attendees] or attendees(lines, lang, patients)
        m = replace(meeting, attendees=people)
        pdf = render_pdf.compile_pdf(render_pdf.tex_source(m, bodies[lang], lang, model, verified),
                                     render_pdf.xmp_source(m, lang, model), out_dir / f"{stem}_{lang}.pdf")
        docx = render_docx.render(m, latexcheck.parse(bodies[lang]), lang, model, verified, out_dir / f"{stem}_{lang}.docx")
        return lang, str(pdf), str(docx)

    with ThreadPoolExecutor(len(langs)) as pool:
        files = {lang: {"pdf": pdf, "docx": docx} for lang, pdf, docx in pool.map(render, langs)}
    timings["render"] = time.perf_counter() - t
    timings["total"] = time.perf_counter() - t0

    facts_path = out_dir / f"{stem}.facts.json"
    fresh(facts_path).write_text(json.dumps({"meeting": to_dict(meeting), "patients": [{"initials": anonymize_text(p["name"], [p]), "age": p["age"], "bed": p["bed"]} for p in patients],
                                      "facts": [to_dict(f) for f in facts]}, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(facts_path, 0o600)
    app_path = out_dir / f"{stem}.meeting.json"   # the web app's Meeting shape, in the first language
    fresh(app_path).write_text(json.dumps(meeting_json(meeting, facts, lines, bodies[langs[0]], langs[0], patients),
                                          ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(app_path, 0o600)
    result = {"files": files, "facts": str(facts_path), "meeting": str(app_path), "checks": counts, "writing": write_reports,
              "timings_s": {k: round(v, 1) for k, v in timings.items()}, "llm": dict(getattr(llm, "stats", {})),
              "lines": len(lines), "model": model,
              "model_digest": llm.digest() if hasattr(llm, "digest") else ""}
    fresh(out_dir / f"{stem}.report.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result
