from types import SimpleNamespace

import numpy as np

from asr_llm.asr import WhisperAsr, rank_languages

SR = 16_000


class FakeWhisper:
    """detect_language returns fixed probs; transcribe scores each language."""

    def __init__(self, probs, scores, texts=None):
        self.probs = probs
        self.scores = scores
        self.texts = texts or {}
        self.decoded = []

    def detect_language(self, samples):
        return self.probs[0][0], self.probs[0][1], self.probs

    def transcribe(self, samples, language, **_):
        self.decoded.append(language)
        text = self.texts.get(language, f"text-{language}")
        seg = SimpleNamespace(start=0.0, end=1.0, text=text, avg_logprob=self.scores[language], no_speech_prob=0.0)
        return iter([seg]), None


def engine(fake):
    asr = WhisperAsr.__new__(WhisperAsr)
    asr._model = fake
    return asr


def test_rank_drops_languages_outside_the_meeting():
    ranked = rank_languages([("lt", 0.5), ("ru", 0.3), ("ro", 0.2)], ("ro", "ru", "en"))
    assert [lang for lang, _ in ranked] == ["ru", "ro"]
    assert abs(ranked[0][1] - 0.6) < 1e-9


def test_confident_wrong_lid_does_not_decide():
    # Measured on the sample: LID says ru 0.9 on Romanian, the ro decode scores better.
    fake = FakeWhisper([("ru", 0.92), ("ro", 0.06)], {"ro": -0.52, "ru": -0.64})
    text, lang = engine(fake).transcribe_batch(np.zeros(SR * 3))
    assert fake.decoded == ["ro", "ru"]
    assert (text, lang) == ("text-ro", "ro")


def test_home_language_wins_close_calls_only():
    close = FakeWhisper([("ru", 0.9)], {"ro": -0.70, "ru": -0.67})
    assert engine(close).transcribe_batch(np.zeros(SR * 3))[1] == "ro"
    clear = FakeWhisper([("ru", 0.9)], {"ro": -0.87, "ru": -0.54})
    assert engine(clear).transcribe_batch(np.zeros(SR * 3))[1] == "ru"


def test_english_decoded_when_lid_says_english():
    fake = FakeWhisper([("en", 0.8), ("ro", 0.1)], {"ro": -0.9, "ru": -1.0, "en": -0.2})
    assert engine(fake).transcribe_batch(np.zeros(SR * 3))[1] == "en"
    assert fake.decoded == ["ro", "ru", "en"]


def test_short_clip_reuses_previous_language():
    fake = FakeWhisper([("ru", 1.0)], {"ro": -0.2, "ru": -0.2})
    _, lang = engine(fake).transcribe_batch(np.zeros(SR // 2), prev_lang="ro")
    assert fake.decoded == ["ro"]
    assert lang == "ro"


def test_subtitle_hallucination_is_dropped():
    fake = FakeWhisper([("ru", 1.0)], {"ro": -0.4, "ru": -0.3}, texts={"ro": "Să vă mulțumim!", "ru": "Продолжение следует..."})
    assert engine(fake).transcribe_batch(np.zeros(SR * 3))[0] == ""
