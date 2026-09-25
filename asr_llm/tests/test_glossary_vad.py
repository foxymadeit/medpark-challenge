from asr_llm.glossary import HOSPITAL_SEED, whisper_initial_prompt
from asr_llm.vad import energy_vad
import numpy as np


def test_whisper_prompt_is_short_and_includes_hospital_terms():
    prompt = whisper_initial_prompt(glossary_path=None)
    assert "CT" in prompt
    assert "pacient" in prompt
    assert len(prompt) < 4000


def test_energy_vad_finds_tone():
    sr = 16_000
    silence = np.zeros(sr, dtype=np.float32)
    t = np.arange(sr, dtype=np.float32) / sr
    tone = 0.2 * np.sin(2 * np.pi * 220 * t)
    audio = np.concatenate([silence, tone, silence])
    spans = energy_vad(audio, sample_rate=sr, pad_s=0.0)
    assert len(spans) == 1
    start, end = spans[0]
    assert 0.8 < start < 1.2
    assert 1.8 < end < 2.2


def test_hospital_seed_covers_three_languages():
    blob = " ".join(HOSPITAL_SEED)
    assert "pacient" in blob
    assert "пациент" in blob
    assert "action item" in blob
