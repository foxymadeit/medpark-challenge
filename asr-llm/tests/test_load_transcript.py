from pathlib import Path

from asr_llm.pipeline import load_transcript


def test_load_kaggle_v2_transcript(tmp_path: Path):
    src = tmp_path / "t.json"
    src.write_text(
        '{"file": "x.m4a", "audio_s": 12.5, "text": "[0.0-2.0] Pacientul are BIPAP.", '
        '"segments": [{"start": 0, "end": 2, "text": "Pacientul are BIPAP.", "language": null}]}',
        encoding="utf-8",
    )
    t = load_transcript(src)
    assert "BIPAP" in t.text
    assert t.duration_s == 12.5
    assert len(t.segments) == 1
