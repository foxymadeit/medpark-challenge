"""Score checked facts against an answer key (eval/meetings.py).

A predicted decision matches a key decision when it cites a line within two
lines of where the key says it was settled; an action, within one line.
Traps are scored on their own: a decision citing only a proposal nobody
adopted, or only a version that was later reversed, is a reasoning error.
"""

import re

_NUM = re.compile(r"(\d+)$")


def _n(line_id: str) -> int:
    return int(line_id[1:])


def _near(evidence, lines, k) -> bool:
    return any(abs(_n(e) - _n(g)) <= k for e in evidence for g in lines)


def _owner_ok(pred: str, gold: str) -> bool:
    a, b = _NUM.search(pred.strip()), _NUM.search(gold.strip())
    return bool(a and b and a.group(1) == b.group(1))


def score_meeting(facts, gold) -> dict:
    kept = [f for f in facts if f.status in ("ok", "confirm")]
    decisions = [f for f in kept if f.kind == "decision"]
    actions = [f for f in kept if f.kind == "action"]
    s = {"decisions_gold": len(gold["decisions"]), "actions_gold": len(gold["actions"]),
         "decisions_pred": len(decisions), "actions_pred": len(actions),
         "dropped": sum(f.status == "dropped" for f in facts), "confirm": sum(f.status == "confirm" for f in facts),
         "downgraded": sum(any("kept as a note" in p for p in f.problems) for f in facts)}

    matched_d = set()
    for key, lines in gold["decisions"].items():
        if any(_near(d.evidence, lines, 2) for d in decisions):
            matched_d.add(key)
    s["decisions_found"] = len(matched_d)
    s["decisions_false"] = sum(1 for d in decisions
                              if not any(_near(d.evidence, l, 2) for l in gold["decisions"].values()))
    s["trap_proposal_errors"] = sum(1 for d in decisions if gold["not_decisions"]
                                    and all(any(abs(_n(e) - _n(t)) <= 0 for t in gold["not_decisions"]) for e in d.evidence))
    s["trap_reversal_errors"] = sum(1 for d in decisions for key, old in gold["old"].items()
                                    if set(d.evidence) <= set(old))

    owners = deadlines = found = 0
    for key, g in gold["actions"].items():
        hit = next((a for a in actions if _near(a.evidence, g["lines"], 1)), None)
        if hit:
            found += 1
            owners += _owner_ok(hit.owner, g["owner"])
            deadlines += (hit.deadline or "") == g["deadline"]
    s["actions_found"], s["owners_right"], s["deadlines_right"] = found, owners, deadlines
    s["actions_false"] = sum(1 for a in actions if not any(_near(a.evidence, g["lines"], 1) for g in gold["actions"].values()))
    return s


def summary(rows) -> dict:
    t = {k: sum(r[k] for r in rows) for k in rows[0]}
    pct = lambda a, b: round(100 * a / b, 1) if b else 0.0  # noqa: E731
    return {
        "decision_recall": pct(t["decisions_found"], t["decisions_gold"]),
        "decision_precision": pct(t["decisions_pred"] - t["decisions_false"], t["decisions_pred"]),
        "action_recall": pct(t["actions_found"], t["actions_gold"]),
        "action_precision": pct(t["actions_pred"] - t["actions_false"], t["actions_pred"]),
        "owner_accuracy": pct(t["owners_right"], t["actions_found"]),
        "deadline_accuracy": pct(t["deadlines_right"], t["actions_found"]),
        "trap_errors": t["trap_proposal_errors"] + t["trap_reversal_errors"],
        "caught_by_verifier": t["dropped"],
        "to_confirm": t["confirm"],
        "downgraded": t["downgraded"],
    }
