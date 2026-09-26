"""Build sample_{ro,ru,en}.docx from the hand-written sample_*.tex, through the
same parser and renderer the pipeline uses, so the two formats can be compared.

  python examples/make_docx.py
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from mom import latexcheck, render_docx  # noqa: E402
from mom.schemas import Meeting  # noqa: E402


def meeting_from(tex: str) -> tuple:
    value = dict(re.findall(r"\\momset\{(\w+)\}\{([^}]*)\}", tex))
    people = [{"name": n, "role": r} for n, r in re.findall(r"\\person\{([^}]*)\}\{([^}]*)\}", tex)]
    start, _, end = value.get("time", "").partition("--")
    d, m, y = value["date"].split(".")
    meeting = Meeting(type="medical", number=value.get("number", ""), date=f"{y}-{m}-{d}", start=start, end=end,
                      place=value.get("place", ""), chair=value.get("chair", ""), secretary=value.get("secretary", ""),
                      attendees=people, quorum=value.get("quorum", ""))
    return meeting, value.get("model", ""), value.get("verified", "")


for lang in ("ro", "ru", "en"):
    tex = (HERE / f"sample_{lang}.tex").read_text(encoding="utf-8")
    body = tex.split("\\end{attendance}", 1)[1].split("\\end{minutes}", 1)[0]
    meeting, model, verified = meeting_from(tex)
    out = render_docx.render(meeting, latexcheck.parse(body), lang, model, verified, HERE / f"sample_{lang}.docx")
    print(out)
