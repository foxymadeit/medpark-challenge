from mom.schemas import Fact, Line
from mom.verify import verify

LINES = [
    Line("L0001", 0, 5, "Speaker 1 (Igor Rusu)", "Ecocardiografia arată o fracție de ejecție de 38 la sută, propun RMN cardiac."),
    Line("L0002", 5, 8, "Speaker 2 (Ana Popescu)", "De acord, aprobăm RMN-ul înainte de intervenția de luni."),
    Line("L0003", 8, 11, "Speaker 1 (Igor Rusu)", "Bine, mă ocup eu de programare până vineri."),
    Line("L0004", 11, 15, "Speaker 3 (Victor Munteanu)", "Poate ar trebui să schimbăm furnizorul de mentenanță."),
]
ATTENDEES = ["Igor Rusu", "Ana Popescu", "Victor Munteanu", "Elena Ciobanu"]


def run(*facts):
    return {f.id: f for f in verify(list(facts), LINES, "2026-09-24", ATTENDEES)}


def test_a_grounded_decision_and_action_pass():
    out = run(Fact("D1", "decision", "Se aprobă RMN-ul înainte de intervenția de luni.", ["L0002"], quote="aprobăm RMN-ul înainte de intervenția de luni"),
              Fact("A1", "action", "Programează RMN-ul.", ["L0003"], quote="mă ocup eu de programare", owner="Igor Rusu", deadline_phrase="până vineri"))
    assert out["D1"].status == "ok" and out["A1"].status == "ok"
    assert out["A1"].deadline == "2026-09-25"


def test_a_quote_that_is_not_in_the_cited_lines_is_dropped():
    out = run(Fact("D1", "decision", "Se aprobă RMN-ul.", ["L0002"], quote="aprobăm tomografia computerizată"))
    assert out["D1"].status == "dropped"


def test_citing_a_line_that_does_not_exist_is_dropped():
    assert run(Fact("N1", "note", "x", ["L0099"], quote="x"))["N1"].status == "dropped"


def test_a_proposal_nobody_accepted_is_a_note_not_a_decision():
    out = run(Fact("D1", "decision", "Se schimbă furnizorul de mentenanță.", ["L0004"], quote="ar trebui să schimbăm furnizorul de mentenanță"))
    assert out["D1"].kind == "note" and "no decision act" in " ".join(out["D1"].problems)


def test_an_owner_who_is_not_in_the_evidence_needs_confirmation():
    out = run(Fact("A1", "action", "Programează RMN-ul.", ["L0003"], quote="mă ocup eu de programare", owner="Elena Ciobanu"))
    assert out["A1"].status == "confirm"


def test_the_speaker_who_says_i_will_do_it_is_a_valid_owner():
    out = run(Fact("A1", "action", "Programează RMN-ul.", ["L0003"], quote="mă ocup eu de programare", owner="Igor Rusu"))
    assert out["A1"].status == "ok"


def test_a_deadline_nobody_said_is_removed():
    out = run(Fact("A1", "action", "Programează RMN-ul.", ["L0003"], quote="mă ocup eu de programare", owner="Igor Rusu", deadline_phrase="până luni", deadline="2026-09-28"))
    assert out["A1"].deadline == "" and out["A1"].deadline_phrase == ""


def test_a_number_that_is_not_in_the_evidence_needs_confirmation():
    out = run(Fact("N1", "note", "Fracția de ejecție este de 45%.", ["L0001"], quote="fracție de ejecție de 38 la sută"))
    assert out["N1"].status == "confirm" and any("45" in p for p in out["N1"].problems)


def test_a_name_that_appears_nowhere_needs_confirmation():
    out = run(Fact("N1", "note", "Dr. Popov a propus RMN cardiac.", ["L0001"], quote="propun RMN cardiac"))
    assert out["N1"].status == "confirm"


def test_a_speaker_label_owner_must_be_the_exact_speaker_of_a_cited_line():
    lines = [Line("L0001", 0, 3, "Speaker 2", "Mă ocup eu de raport până vineri."),
             Line("L0002", 3, 6, "Speaker 5", "Bine.")]
    ok = verify([Fact("A1", "action", "Pregătește raportul.", ["L0001"], quote="mă ocup eu de raport", owner="Speaker 2")], lines, "2026-09-24")
    wrong = verify([Fact("A1", "action", "Pregătește raportul.", ["L0001"], quote="mă ocup eu de raport", owner="Speaker 5")], lines, "2026-09-24")
    assert ok[0].status == "ok" and wrong[0].status == "confirm"
    assert verify([Fact("A1", "action", "x", ["L0001"], quote="mă ocup eu de raport", owner="Vorbitorul 2")], lines, "2026-09-24")[0].status == "ok"
