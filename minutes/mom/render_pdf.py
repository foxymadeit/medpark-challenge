"""Checked body + meeting details -> the Medpark PDF (XeLaTeX, PDF/A-2b).

Everything our code puts in the document goes through latexcheck.escape.
The model's body has already passed latexcheck.parse. XeLaTeX runs with
shell escape off and file access restricted to the working folder.
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import latexcheck
from .schemas import Meeting, format_date

TEMPLATE = Path(__file__).resolve().parent.parent / "template"
DOC_WORD = {"ro": "Proces-verbal", "ru": "Протокол", "en": "Minutes"}
LANG_TAG = {"ro": "ro-MD", "ru": "ru", "en": "en-GB"}
RERUN = re.compile(r"Rerun to get|Label\(s\) may have changed|Table widths have changed|may have changed\. Rerun")


def tex_source(meeting: Meeting, body: str, lang: str, model: str, verified: str) -> str:
    e = latexcheck.escape
    time = f"{e(meeting.start)}--{e(meeting.end)}" if meeting.start and meeting.end else e(meeting.start)
    sets = {"number": meeting.number or "1", "title": meeting.title(lang), "date": format_date(meeting.date, lang),
            "time": time, "place": meeting.place, "chair": meeting.chair, "secretary": meeting.secretary,
            "model": model, "verified": verified}
    if meeting.quorum:
        sets["quorum"] = meeting.quorum
    lines = [f"\\def\\momtemplatedir{{{TEMPLATE.as_posix()}/}}", "\\documentclass{medpark-mom}", f"\\momlanguage{{{lang}}}"]
    lines += [f"\\momset{{{k}}}{{{v if k == 'time' else e(v)}}}" for k, v in sets.items()]  # time is pre-escaped
    lines += ["\\begin{document}", "\\begin{minutes}", _attendance(meeting), body.strip()]
    if meeting.next_meeting and "\\nextmeeting" not in body:
        lines.append(f"\\nextmeeting{{{e(meeting.next_meeting)}}}")
    lines += ["\\end{minutes}", "\\end{document}", ""]
    return "\n".join(lines)


def _attendance(meeting: Meeting) -> str:
    """Written by code from the checked attendee list, never by the model."""
    e = latexcheck.escape
    out = []
    for key, people in (("present", meeting.attendees), ("apologies", meeting.apologies)):
        if people:
            out.append(f"\\begin{{attendance}}{{{key}}}")
            out += [f"\\person{{{e(p.get('name', ''))}}}{{{e(p.get('role', ''))}}}" for p in people]
            out.append("\\end{attendance}")
    return "\n".join(out)


def xmp_source(meeting: Meeting, lang: str, model: str) -> str:
    """AI Act Art. 50(2): machine-readable marking that the text is AI-generated."""
    e = latexcheck.escape
    return "\n".join([
        f"\\Title{{{DOC_WORD[lang]} {e(meeting.title(lang))}}}",
        f"\\Author{{Secure MOM (AI-generated, local model {e(model)})}}",
        "\\Subject{AI-generated minutes of meeting. Drafted locally by an AI system and reviewed by the chair before sending.}",
        "\\Keywords{AI-generated\\sep Secure MOM\\sep minutes of meeting\\sep Medpark}",
        f"\\Language{{{LANG_TAG[lang]}}}",
        "\\Publisher{Medpark International Hospital}", ""])


def compile_pdf(tex: str, xmp: str, out_pdf: Path) -> Path:
    """Compile in a private temporary folder; only the PDF comes out."""
    out_pdf = Path(out_pdf)
    with tempfile.TemporaryDirectory(prefix="mom-") as tmp:
        work = Path(tmp)
        (work / "doc.tex").write_text(tex, encoding="utf-8")
        (work / "doc.xmpdata").write_text(xmp, encoding="utf-8")
        env = {**os.environ, "TEXINPUTS": f"{TEMPLATE.as_posix()}//:", "openout_any": "p", "openin_any": "p",
               "shell_escape": "f"}
        run = None
        for n, extra in enumerate((["-no-pdf"], [], [])):  # pass 1 writes page count and table widths
            run = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", *extra, "doc.tex"],
                                 cwd=work, env=env, capture_output=True, text=True, timeout=120)
            log = (work / "doc.log").read_text(errors="ignore") if (work / "doc.log").exists() else ""
            if run.returncode != 0 or (n >= 1 and not RERUN.search(log)):
                break
        pdf = work / "doc.pdf"
        if run.returncode != 0 or not pdf.exists():
            log = (work / "doc.log").read_text(errors="ignore") if (work / "doc.log").exists() else run.stdout
            errors = [l for l in log.splitlines() if l.startswith("!")][:5]
            raise RuntimeError("LaTeX failed: " + (" | ".join(errors) or run.stderr[-400:]))
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pdf, out_pdf)
        os.chmod(out_pdf, 0o600)
    return out_pdf
