from asr_llm.glossary import load_glossary
from asr_llm.config import settings
from asr_llm.vad import speech_spans
import numpy as np


def test_glossary_has_three_languages():
    data = load_glossary()
    assert len(data["aligned"]) >= 50
    sample = data["aligned"][0]
    assert sample["ro"] and sample["ru"] and sample["en"]
    assert any(row["ro"] == "pacient" for row in data["aligned"])


def test_vad_cuts_real_speech_and_ignores_silence(meeting_audio):
    spans = speech_spans(meeting_audio)
    assert len(spans) >= 3
    assert all(end - start <= settings.max_batch_s + 1 for start, end in spans)
    assert speech_spans(np.zeros(16_000 * 3, dtype=np.float32)) == []
