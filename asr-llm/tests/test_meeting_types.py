from asr_llm.llm import LocalLlm, sample_lines
from asr_llm.meeting_types import MEETING_TYPES, definitions_block, focus_for
from asr_llm.schemas import SpeechSegment, Transcript


class FakeLlm(LocalLlm):
    def __init__(self, detected):
        self.detected = detected
        self.systems = []

    def chat_json(self, system, user, max_tokens):
        self.systems.append(system)
        if system.startswith("You sort hospital meetings"):
            return self.detected
        return {"title": "t", "summary": "s", "decisions": [], "action_items": []}


def transcript(text="[0.0-2.0] Bugetul pe trimestru e 2 milioane lei."):
    return Transcript(
        source="x", duration_s=2, asr_device="cpu", asr_model="m",
        segments=[SpeechSegment(start=0, end=2, text=text)], text=text,
    )


def test_no_choice_uses_detected_type_and_its_focus():
    llm = FakeLlm({"meeting_type": "executive", "reason": "budget figures"})
    minutes = llm.extract_minutes(transcript())
    assert (minutes.meeting_type, minutes.meeting_type_detected) == ("executive", "executive")
    assert minutes.meeting_type_reason == "budget figures"
    assert MEETING_TYPES["executive"]["focus"] in llm.systems[-1]


def test_user_choice_wins_but_detection_is_kept():
    llm = FakeLlm({"meeting_type": "executive", "reason": "budget figures"})
    minutes = llm.extract_minutes(transcript(), meeting_type="medical")
    assert (minutes.meeting_type, minutes.meeting_type_detected) == ("medical", "executive")
    assert MEETING_TYPES["medical"]["focus"] in llm.systems[-1]


def test_unusable_detection_falls_back():
    minutes = FakeLlm({"meeting_type": "party"}).extract_minutes(transcript())
    assert (minutes.meeting_type, minutes.meeting_type_detected) == ("administrative", None)


def test_sample_spans_the_whole_meeting_within_budget():
    text = "\n".join(f"line {i:03d} " + "x" * 40 for i in range(300))
    sample = sample_lines(text, 2000)
    assert len(sample) <= 2000
    assert "line 000" in sample and "line 2" in sample


def test_definitions_cover_all_types_and_tie_breaks():
    block = definitions_block()
    assert all(name.upper() in block for name in MEETING_TYPES)
    assert "Medical supplies" in block
    assert "What these minutes must capture" in focus_for("administrative")
