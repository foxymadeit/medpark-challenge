import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "kaggle_asr_bakeoff"))
from summarize import keeps_russian  # noqa: E402


def test_a_setup_that_loses_the_russian_cannot_become_the_default():
    assert not keeps_russian({"gold": {"cer_ru_part": 0.0}, "clip_team1": {"cer_ru_part": 1.0}})
    assert keeps_russian({"clip_team1": {"cer_ru_part": 0.44}, "clip_team2": {"cer_ru_part": 0.41}})
    assert keeps_russian({"clip_team1": {"cer_ru_part": None}})
