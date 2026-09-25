import numpy as np

from diarizer import voices
from diarizer.passages import PASSAGES


def test_each_passage_takes_about_25_seconds_to_read():
    for lang, text in PASSAGES.items():
        words = len(text.split())
        assert 45 <= words <= 75, (lang, words)  # 2 to 3 words a second
        assert "?" in text  # one question, for the rising pitch


def test_adding_a_second_language_keeps_the_first(tmp_path, monkeypatch):
    monkeypatch.setattr(voices, "VOICES_DIR", tmp_path)
    voices.save_voice("Dr. Ana Popescu", "titanet-small", [np.ones(4)] * 3)
    voices.save_voice("Dr. Ana Popescu", "titanet-small", [np.zeros(4)] * 2, add=True)
    assert len(voices.load_voices("titanet-small")["Dr. Ana Popescu"]) == 5
    voices.save_voice("Dr. Ana Popescu", "titanet-small", [np.ones(4)])
    assert len(voices.load_voices("titanet-small")["Dr. Ana Popescu"]) == 1


def test_closest_voice_names_the_person_a_new_voice_could_be_confused_with():
    a, b = np.array([1.0, 0, 0]), np.array([0, 1.0, 0])
    known = {"Elena Ciobanu": [a, a], "Igor Rusu": [b]}
    name, sim = voices.closest_voice([np.array([0.9, 0.1, 0])], known)
    assert name == "Elena Ciobanu" and sim > 0.9
    assert voices.closest_voice([a], {}) == (None, 0.0)
    assert voices.closest_voice([a], known, skip="Elena Ciobanu")[0] == "Igor Rusu"
