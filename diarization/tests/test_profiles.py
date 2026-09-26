import numpy as np

from diarizer.profiles import CLOSE_ABOVE_DB, PROFILES, pick, speech_to_background_db

SR = 16000


class LoudFrames:
    """Stand-in segmenter: a frame is speech when it is loud."""
    hop, receptive = 270, 991

    def __call__(self, audio):
        n = (len(audio) - self.receptive) // self.hop + 1
        e = np.array([np.mean(audio[i * self.hop:i * self.hop + self.receptive] ** 2) for i in range(n)])
        return (e > 0.003)[:, None] & np.array([[True, False, False]])

    def frame_span(self, i):
        c = i * self.hop + self.receptive // 2
        return c - self.hop // 2, c + self.hop - self.hop // 2


def _talk(snr_db, seconds=20, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(seconds * SR) / SR
    speech = 0.1 * np.sin(2 * np.pi * 200 * t) * (np.sin(2 * np.pi * 0.25 * t) > 0)
    noise = rng.standard_normal(t.size) * 0.1 / np.sqrt(2) / 10 ** (snr_db / 20)
    return (speech + noise).astype(np.float32)


def test_measures_speech_against_background_within_a_few_db():
    for true_db in (5.0, 25.0):
        got = speech_to_background_db(_talk(true_db), LoudFrames())
        assert abs(got - true_db) < 4, (true_db, got)


def test_quiet_rooms_go_close_and_echoing_rooms_go_far():
    assert pick(CLOSE_ABOVE_DB + 5) == "close"
    assert pick(CLOSE_ABOVE_DB - 5) == "far"
    assert pick(float("nan")) == "far"  # no silence to measure: assume the harder case


def test_both_profiles_name_their_models_and_thresholds():
    for p in PROFILES.values():
        assert p["segmentation"].endswith(".onnx")
        assert 0 < p["new"] < p["assign"] < 1 and 0 < p["merge"] <= 1
