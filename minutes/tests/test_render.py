import json
import shutil
import subprocess
from pathlib import Path

import pytest
from docx import Document

from mom import latexcheck, render_docx, render_pdf
from mom.schemas import Meeting

BODY = r"""
\begin{agenda}
\agendaitem{T1}{Contractul RMN}
\end{agenda}
\topic{T1}{Contractul RMN}
\presented{N1}{dl Victor Munteanu}{Dl Victor Munteanu a comunicat că reducerea este de 10\%.}
\decision{D1}{Se aprobă reînnoirea contractului.}{în unanimitate}
\action{A1}{dl Victor Munteanu}{}{Verifică condițiile.}
\needsconfirmation{C1}{Cine trimite documentele.}
"""
MEETING = Meeting(type="medical", number="7", date="2026-09-26", start="14:00", end="14:30", place="Sala {1} & 50%",
                  chair=r"dna Ana POPESCU \input{x}", secretary="dna Elena Ciobanu",
                  attendees=[{"name": "dna Ana Popescu", "role": "director medical"}])


def test_docx_has_every_fact_the_ai_marking_and_private_permissions(tmp_path):
    out = render_docx.render(MEETING, latexcheck.parse(BODY), "ro", "test-model", "4/4", tmp_path / "m.docx")
    doc = Document(out)
    text = "\n".join(p.text for p in doc.paragraphs) + "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    for needle in ("PROCES-VERBAL nr. 7", "Se aprobă reînnoirea contractului.", "Verifică condițiile.", "reducerea este de 10%"):
        assert needle in text, needle
    assert "nestabilit" not in text and "Cine trimite documentele." not in text
    assert "AI-generated" in doc.core_properties.keywords and "test-model" in doc.core_properties.author
    assert oct(out.stat().st_mode & 0o777) == "0o600"


def test_labels_come_from_the_latex_class_in_every_language():
    for lang, word in (("ro", "PROCES-VERBAL"), ("ru", "ПРОТОКОЛ"), ("en", "MINUTES")):
        s = render_docx.strings(lang)
        assert s["doc"] == word and s["owner"] and s["aifooter"]


def test_header_values_are_escaped_before_they_reach_latex():
    tex = render_pdf.tex_source(MEETING, BODY, "ro", "m", "4/4")
    assert r"\input{x}" not in tex and r"Sala (1) \& 50\%" in tex


@pytest.mark.skipif(not shutil.which("latexmk"), reason="needs TeX Live")
def test_pdf_compiles_with_ai_marking_in_its_metadata(tmp_path):
    pdf = render_pdf.compile_pdf(render_pdf.tex_source(MEETING, BODY, "ro", "test-model", "4/4"),
                                 render_pdf.xmp_source(MEETING, "ro", "test-model"), tmp_path / "m.pdf")
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    assert "AI-generated" in info and "test-model" in info
    text = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout
    assert "Se aprobă reînnoirea contractului." in text and "PROCES-VERBAL" in text


def _saved_state(tmp_path, lang="en"):
    """A render file as the pipeline leaves it, for one language."""
    from mom.schemas import to_dict
    state = {"meeting": to_dict(MEETING), "bodies": {lang: BODY}, "attendees": {lang: MEETING.attendees},
             "model": "test-model", "verified": "4/4"}
    path = tmp_path / "MoM_2026-09-26_medical.render.json"
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.skipif(not shutil.which("latexmk"), reason="needs TeX Live")
def test_rerender_files_and_titles_the_documents_under_the_new_type(tmp_path):
    from mom.pipeline import rerender
    result = rerender(_saved_state(tmp_path), "executive")
    pdf, docx = Path(result["files"]["en"]["pdf"]), Path(result["files"]["en"]["docx"])
    assert pdf.name == "MoM_2026-09-26_executive_en.pdf" and docx.name == "MoM_2026-09-26_executive_en.docx"
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    title = next(l for l in info.splitlines() if l.startswith("Title:"))
    assert "Executive Committee" in title and "Medical" not in title
    assert "Executive Committee" in Document(docx).core_properties.title
    assert oct(pdf.stat().st_mode & 0o777) == "0o600" and oct(docx.stat().st_mode & 0o777) == "0o600"
    moved = tmp_path / "MoM_2026-09-26_executive.render.json"   # the render file follows the type, once
    assert result["render"] == str(moved) and oct(moved.stat().st_mode & 0o777) == "0o600"
    assert json.loads(moved.read_text())["meeting"]["type"] == "executive"
    assert not (tmp_path / "MoM_2026-09-26_medical.render.json").exists()


def test_rerender_refuses_an_unknown_type_or_a_body_that_breaks_the_rules(tmp_path):
    from mom.latexcheck import BodyError
    from mom.pipeline import rerender
    with pytest.raises(ValueError, match="meeting type"):
        rerender(_saved_state(tmp_path), "board-of-evil")
    path = _saved_state(tmp_path)
    state = json.loads(path.read_text())
    state["bodies"]["en"] = BODY + "\n\\input{/etc/passwd}"
    path.write_text(json.dumps(state))
    with pytest.raises(BodyError):
        rerender(path, "executive")


@pytest.mark.skipif(not shutil.which("latexmk"), reason="needs TeX Live")
def test_mom_render_command(tmp_path, capsys):
    from mom.cli import main
    main(["render", str(_saved_state(tmp_path)), "--type", "administrative"])
    assert (tmp_path / "MoM_2026-09-26_administrative_en.pdf").is_file()
    assert "MoM_2026-09-26_administrative_en.docx" in capsys.readouterr().out
