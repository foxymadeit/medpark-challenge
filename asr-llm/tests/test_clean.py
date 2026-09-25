from asr_llm.clean import collapse_repeat_segments, ground_minutes
from asr_llm.llm import lock_translation
from asr_llm.schemas import ActionItem, Minutes, SpeechSegment


def _seg(start: float, text: str) -> SpeechSegment:
    return SpeechSegment(start=start, end=start + 1, text=text)


def test_collapse_keeps_a_double_and_folds_a_loop():
    segments = [
        _seg(0, "Da."),
        _seg(1, "Da."),
        _seg(2, "Pacientul are stent."),
        _seg(3, "Nici nu au avut."),
        _seg(4, "Nici nu au avut"),
        _seg(5, "Nici nu au avut."),
        _seg(6, "Mergem mai departe."),
    ]
    kept = collapse_repeat_segments(segments)
    assert [s.text for s in kept] == ["Da.", "Da.", "Pacientul are stent.", "Nici nu au avut.", "Mergem mai departe."]
    assert kept[3].end == 6


def test_ground_drops_names_and_quotes_missing_from_the_transcript():
    minutes = Minutes(
        title="Runda",
        meeting_type="medical",
        summary="Pe scurt.",
        attendees=["Ana Pop", "Nume1", "Stent"],
        action_items=[
            ActionItem(text="Continuăm noradrenalina.", source_quote="noradrenalina 0,07"),
            ActionItem(text="Inventat.", source_quote="această frază nu există"),
        ],
    )
    grounded = ground_minutes(minutes, "Ana Pop spune: noradrenalina 0,07. Stentul este pe stânga.")
    assert grounded.attendees == ["Ana Pop"]
    assert grounded.action_items[0].source_quote == "noradrenalina 0,07"
    assert grounded.action_items[1].source_quote is None


def test_translation_keeps_quotes_and_names():
    source = Minutes(
        title="Runda",
        meeting_type="medical",
        language="ro",
        summary="Pe scurt.",
        attendees=["Ana Pop"],
        decisions=["Continuăm."],
        action_items=[ActionItem(text="Continuăm noradrenalina.", owner=None, source_quote="noradrenalina 0,07")],
    )
    translated = Minutes(
        title="Round",
        meeting_type="executive",
        language="xx",
        summary="In short.",
        attendees=["Someone Else"],
        decisions=["We continue."],
        action_items=[ActionItem(text="Continue noradrenaline.", owner="Invented", source_quote="rewritten quote")],
    )
    locked = lock_translation(source, translated, "en")
    assert locked.language == "en"
    assert locked.attendees == ["Ana Pop"]
    assert locked.meeting_type == "medical"
    assert locked.summary == "In short."
    assert locked.action_items[0].text == "Continue noradrenaline."
    assert locked.action_items[0].source_quote == "noradrenalina 0,07"
    assert locked.action_items[0].owner is None
