"""Meeting types: how to tell them apart, and what the minutes should focus on.

Plain text on purpose, so the team can review and edit it without touching the
prompt code. Used twice: to detect the type from the transcript, and to steer
what the minutes extract once the type is known.
"""

from __future__ import annotations

MEETING_TYPES: dict[str, dict[str, str]] = {
    "medical": {
        "definition": (
            "Clinical discussion of specific patients or cases: presentation of a case, examination, lab and imaging "
            "results, diagnosis, treatment and medication, procedures and surgery, transfers between departments, "
            "consultations with other specialists, prognosis and follow-up. The main content is medical information "
            "about patients."
        ),
        "attendees": "Physicians, residents, nurses, medical board members, heads of clinical departments.",
        "signals": (
            "Patients referred to by bed, room, age or case (\"pacientul de pe patul 9\", \"больной в 4-й палате\"); "
            "diagnoses; drugs and doses (\"noradrenalină 0,2\"); vital signs and lab values (\"TA 80 pe 40\", "
            "\"creatinina 240\"); procedures (\"ecografie\", \"КТ\", \"stent\"); ward rounds and case reviews."
        ),
        "focus": (
            "Organise by patient in the order discussed, identified only as the speakers identify them (bed, case). "
            "For each: current status and key findings, what was decided (diagnostics, treatment, transfer, "
            "consultation), who is responsible, and when (\"până diseară\", \"завтра утром\"). Keep drug names, doses "
            "and lab values exactly as spoken. Never add a diagnosis, dose or value that was not said."
        ),
    },
    "executive": {
        "definition": (
            "Strategic and financial direction of the hospital: strategy, macro plans, budgets, revenue, costs and "
            "investments, KPIs and targets, large projects, partnerships, expansion, organisational changes at "
            "management level."
        ),
        "attendees": "CEO, board members, directors, top managers and other executives.",
        "signals": (
            "Sums of money with a currency or period (\"2 milioane lei\", \"бюджет на квартал\", \"ROI\"); percentages "
            "and targets; quarters and years; approval of projects or investments; management titles; market, "
            "competitors, growth; high-level decisions that apply to the whole hospital or a whole department."
        ),
        "focus": (
            "Decisions and approvals first. Keep every figure exactly as spoken with its currency, unit and period. "
            "Then strategic initiatives and projects with owner (director level), milestones and deadlines, and open "
            "risks or questions to be brought back to the next meeting."
        ),
    },
    "administrative": {
        "definition": (
            "Running the hospital outside clinical care and outside strategy: facilities and housekeeping, cleaning "
            "and maintenance, security and access control, IT and equipment, procurement, stock and inventory "
            "(including medical supplies as goods), suppliers, schedules and shifts, staff logistics, internal rules "
            "and compliance procedures, parking, catering."
        ),
        "attendees": "Department and unit heads, administrators, operations, procurement, IT, security and facility staff.",
        "signals": (
            "Orders, deliveries, stock levels and suppliers (\"stocul de mănuși\", \"поставщик\"); repairs and "
            "maintenance; security incidents and access; rosters and shifts; policies and paperwork; no discussion "
            "of individual patients' treatment."
        ),
        "focus": (
            "Operational tasks as who does what by when, with quantities and item names exactly as spoken (orders, "
            "stock, repairs). Note issues raised and their agreed fix, and anything escalated to management."
        ),
    },
}

RULES = """How to decide when a meeting touches several areas:
- Clinical details about specific patients dominate -> medical, even if costs or supplies are mentioned.
- Medical supplies, drugs or equipment discussed as stock, orders or deliveries, without patient care -> administrative.
- Money discussed as strategy, budget or investment decisions at management level -> executive; routine purchase costs -> administrative.
- A mixed meeting gets the type that covers most of the discussion time; name the secondary type in the reason.
- Decide from what is said, not from who is present."""


def definitions_block() -> str:
    """All three types plus the tie-break rules, for the classifier prompt."""
    parts = []
    for name, info in MEETING_TYPES.items():
        parts.append(
            f"{name.upper()}\n"
            f"Definition: {info['definition']}\n"
            f"Typical attendees: {info['attendees']}\n"
            f"Signals: {info['signals']}"
        )
    return "\n\n".join(parts) + "\n\n" + RULES


def focus_for(meeting_type: str) -> str:
    info = MEETING_TYPES[meeting_type]
    return f"This is a {meeting_type} meeting: {info['definition']}\nWhat these minutes must capture: {info['focus']}"
