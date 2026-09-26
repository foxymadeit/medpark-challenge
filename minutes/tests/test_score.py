from eval.score import score_meeting, summary
from mom.schemas import Fact

GOLD = {"decisions": {"mri": ["L0009"], "time": ["L0014"]}, "actions": {"book": {"lines": ["L0010"], "owner": "Speaker 2", "deadline": "2026-09-25"}},
        "old": {"time": ["L0011"]}, "not_decisions": ["L0020"], "patients": []}


def test_scoring_counts_hits_traps_owners_and_deadlines():
    facts = [Fact("D1", "decision", "RMN", ["L0007", "L0009"]),
             Fact("D2", "decision", "ora 9", ["L0011"]),                 # reversed version: reasoning error
             Fact("D3", "decision", "furnizor", ["L0020"]),              # proposal nobody adopted
             Fact("A1", "action", "programare", ["L0010"], owner="Participantul 2", deadline="2026-09-25"),
             Fact("N1", "note", "x", ["L0001"], status="dropped")]
    s = score_meeting(facts, GOLD)
    assert s["decisions_found"] == 1 and s["trap_reversal_errors"] == 1 and s["trap_proposal_errors"] == 1
    assert s["owners_right"] == 1 and s["deadlines_right"] == 1 and s["dropped"] == 1
    out = summary([s])
    assert out["decision_recall"] == 50.0 and out["action_recall"] == 100.0 and out["trap_errors"] == 2
