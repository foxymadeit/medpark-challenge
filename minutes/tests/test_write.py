from mom import latexcheck
from mom.schemas import Fact
from mom.write import check_body, fallback_body, owner_display, plan, write_body

FACTS = [
    Fact("T1", "topic", "Contractul RMN", ["L0001"], quote="x"),
    Fact("N1", "note", "Contractul expiră la sfârșitul lunii.", ["L0001"], quote="x", topic="T1"),
    Fact("D1", "decision", "Se reînnoiește contractul.", ["L0002"], quote="x", topic="T1", vote="pro 4, contra 0"),
    Fact("A1", "action", "Verifică condițiile.", ["L0003"], quote="x", topic="T1", owner="Speaker 3", deadline="2026-09-30"),
    Fact("A2", "action", "Trimite documentele.", ["L0004"], quote="x", topic="T1", owner="Elena Rusu", status="confirm"),
    Fact("N9", "note", "dropped", ["L0009"], quote="x", topic="T1", status="dropped"),
]
EVIDENCE = {"N1": "contractul expiră la sfârșitul lunii", "D1": "aprobăm, pro 4, contra 0", "A1": "verific eu până pe 30", "A2": "cineva trimite"}
GOOD = r"""\begin{agenda}
\agendaitem{T1}{Contractul RMN}
\end{agenda}
\topic{T1}{Contractul RMN}
\noted{N1}{S-a comunicat că contractul expiră la sfârșitul lunii.}
\decision{D1}{Se aprobă reînnoirea contractului.}{pro 4, contra 0}
\action{A1}{Participantul 3}{30.09.2026}{Verifică condițiile de reînnoire.}
\needsconfirmation{C1}{Trimiterea documentelor.}"""


def test_plan_orders_facts_localises_owners_and_dates_and_hides_dropped_ones():
    rows = plan(FACTS, "ru")
    assert [r["id"] for r in rows] == ["T1", "N1", "D1", "A1", "C1"]
    assert rows[3]["owner"] == "Участник 3" and rows[3]["deadline"] == "30.09.2026"
    assert plan(FACTS, "en")[3]["deadline"] == "30 September 2026"
    assert owner_display("SPEAKER_07", "ro") == "Participantul 07" and owner_display("dna Ana Popescu", "ro") == "dna Ana Popescu"


def test_a_correct_body_passes_and_owners_are_forced_to_the_given_values():
    rows = plan(FACTS, "ro")
    body, errors = check_body(GOOD.replace("{Participantul 3}", "{Dr. Invented}"), rows, EVIDENCE)
    assert errors == [] and "{Participantul 3}" in body


def test_missing_ids_invented_numbers_patients_and_wrong_script_are_caught():
    rows = plan(FACTS, "ro")
    body, errors = check_body(GOOD.replace(r"\noted{N1}{S-a comunicat că contractul expiră la sfârșitul lunii.}", ""), rows, EVIDENCE)
    assert any("N1 appears 0 times" in e for e in errors)
    _, errors = check_body(GOOD.replace("expiră la", "expiră în 45 de zile, la"), rows, EVIDENCE)
    assert any("45" in e for e in errors)
    body, _ = check_body(GOOD.replace("Trimiterea documentelor.", "Pacienta Maria Lungu."), rows, EVIDENCE, patients=[{"name": "Maria Lungu"}])
    assert "Maria Lungu" not in body and "M.L." in body
    _, errors = check_body(GOOD.replace("Trimiterea documentelor.", "Отправка документов."), rows, EVIDENCE)
    assert any("Cyrillic" in e for e in errors)


def test_fallback_body_always_parses():
    latexcheck.parse(fallback_body(plan(FACTS, "en")))


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)

    def chat(self, *a, **k):
        return self.replies.pop(0)


def test_write_body_repairs_once_then_falls_back():
    body, rep = write_body(FakeLLM(["```latex\n" + GOOD + "\n```"]), FACTS, "ro", EVIDENCE)
    assert rep["source"] == "model" and latexcheck.parse(body)
    body, rep = write_body(FakeLLM(["\\input{x}", GOOD]), FACTS, "ro", EVIDENCE)
    assert rep["source"] == "model, repaired"
    body, rep = write_body(FakeLLM(["\\input{x}", "\\input{y}"]), FACTS, "ro", EVIDENCE)
    assert rep["source"] == "fallback" and latexcheck.parse(body)
