from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "Medpark_audio.m4a"


@pytest.fixture(scope="session")
def meeting_audio():
    """First 30 s of the organizers' anonymized sample, 16 kHz mono."""
    if not SAMPLE.exists():
        pytest.skip("sample recording not present")
    from asr_llm.audio import decode_audio

    return decode_audio(SAMPLE)[: 16_000 * 30]
