from asr_llm.schemas import SpeechSegment
from asr_llm.score import error_rate, report, script_mismatch


def test_error_rate():
    assert error_rate(list("abc"), list("abc")) == 0
    assert error_rate(list("abc"), list("abd")) == 1 / 3
    assert error_rate("a b".split(), []) == 1.0


def test_script_mismatch_catches_cyrillic_romanian():
    assert script_mismatch(SpeechSegment(start=0, end=1, text="Ело фост", language="ro"))
    assert script_mismatch(SpeechSegment(start=0, end=1, text="El a fost", language="ru"))
    assert not script_mismatch(SpeechSegment(start=0, end=1, text="El a fost", language="ro"))
    assert not script_mismatch(SpeechSegment(start=0, end=1, text="Да, да", language="ru"))


def test_report_counts_and_window():
    segs = [
        SpeechSegment(start=0, end=2, text="Pacientul are hipertensiune", language="ro"),
        SpeechSegment(start=3, end=4, text="Iešunčiui", language="lt"),
        SpeechSegment(start=200, end=201, text="ignored outside window", language="en"),
    ]
    out = report(segs, gold="Pacientul are hipertensiune. Iešunčiui", window_s=180)
    assert out["off_set_lid"] == 1
    assert out["cer"] == 0.0


def test_changes_counts_direction():
    from asr_llm.score import changes

    base = [SpeechSegment(start=0, end=1, text="a", language="ro"), SpeechSegment(start=1, end=2, text="b", language="ru")]
    other = [SpeechSegment(start=0, end=1, text="x", language="ru"), SpeechSegment(start=1, end=2, text="b", language="ru")]
    assert changes(base, other) == {"changed": 1, "by_direction": {"ro->ru": 1}}
