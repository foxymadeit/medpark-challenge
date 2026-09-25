from asr_llm.glossary import asr_hotwords, llm_term_table, load_glossary, whisper_initial_prompt
from asr_llm.vad import energy_vad
import numpy as np


def test_glossary_has_three_languages():
    data = load_glossary()
    assert len(data["aligned"]) >= 50
    sample = data["aligned"][0]
    assert sample["ro"] and sample["ru"] and sample["en"]
    assert any(row["ro"] == "pacient" for row in data["aligned"])


def test_asr_lists_stay_short():
    hot = asr_hotwords()
    prompt = whisper_initial_prompt()
    assert "CT" in hot or "CT" in prompt
    assert "пациент" in hot or "пациент" in prompt
    assert len(prompt) < 4000
    assert len(hot) < 8000


def test_llm_table_is_aligned():
    table = llm_term_table()
    assert "ro | ru | en" in table
    assert "Hipertensiune" in table or "hipertensiune" in table.lower()
    assert "гипертензия" in table.lower() or "Гипертензия" in table


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
