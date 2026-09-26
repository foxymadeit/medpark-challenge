from types import SimpleNamespace

import numpy as np

from asr_llm.asr import WhisperAsr, candidate_languages, rank_languages

SR = 16_000


class FakeWhisper:
    """detect_language returns fixed probs; transcribe scores each language."""

    def __init__(self, probs, scores):
        self.probs = probs
        self.scores = scores
        self.decoded = []

    def detect_language(self, samples):
        return self.probs[0][0], self.probs[0][1], self.probs

    def transcribe(self, samples, language, **_):
        self.decoded.append(language)
        seg = SimpleNamespace(start=0.0, end=1.0, text=f"text-{language}", avg_logprob=self.scores[language], no_speech_prob=0.0)
        return iter([seg]), None


def engine(fake):
    asr = WhisperAsr.__new__(WhisperAsr)
    asr._model = fake
    return asr


def test_rank_drops_languages_outside_the_meeting():
    ranked = rank_languages([("lt", 0.5), ("ru", 0.3), ("ro", 0.2)], ("ro", "ru", "en"))
    assert [lang for lang, _ in ranked] == ["ru", "ro"]
    assert abs(ranked[0][1] - 0.6) < 1e-9


def test_margin_adds_second_candidate():
    assert candidate_languages([("ru", 0.55), ("ro", 0.45)], margin=0.25) == ["ru", "ro"]
    assert candidate_languages([("ru", 0.9), ("ro", 0.1)], margin=0.25) == ["ru"]


def test_close_call_keeps_the_more_confident_decode():
    fake = FakeWhisper([("lt", 0.5), ("ru", 0.26), ("ro", 0.24)], {"ru": -0.9, "ro": -0.3})
    text, lang = engine(fake).transcribe_batch(np.zeros(SR * 3), prev_lang=None)
    assert fake.decoded == ["ru", "ro"]
    assert (text, lang) == ("text-ro", "ro")


def test_short_clip_reuses_previous_language():
    fake = FakeWhisper([("ru", 1.0)], {"ro": -0.2, "ru": -0.2})
    text, lang = engine(fake).transcribe_batch(np.zeros(SR // 2), prev_lang="ro")
    assert fake.decoded == ["ro"]
    assert lang == "ro"
