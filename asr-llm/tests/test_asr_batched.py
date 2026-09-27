import numpy as np

from asr_llm.asr import _winner, transcribe_batches
from asr_llm.asr_batched import short_languages, split_window
from asr_llm.batching import AudioBatch

TS = 50_000  # stand-in for the tokenizer's first timestamp token


def test_short_utterances_take_the_language_the_previous_one_came_out_in():
    short = [False, True, True, False, True]
    assert short_languages(short, {0: "ro", 3: "ru"}) == {1: "ro", 2: "ro", 4: "ru"}


def test_a_window_ending_on_one_timestamp_is_complete():
    tokens = [TS, 10, 11, TS + 100, TS + 100, 12, TS + 250]
    segments, complete = split_window(tokens, TS, content_frames=600)
    assert complete
    assert [(s, e) for s, e, _ in segments] == [(0, 100), (100, 250)]


def test_a_window_stopping_early_needs_the_old_path():
    # ends on two timestamps at 3 s of an 8 s utterance: faster-whisper decodes from 3 s again
    tokens = [TS, 10, TS + 150, TS + 150]
    assert split_window(tokens, TS, content_frames=800)[1] is False
    # the same pair at the very end covers the utterance
    assert split_window(tokens, TS, content_frames=300)[1] is True


def test_a_window_without_timestamp_pairs_is_one_segment():
    segments, complete = split_window([TS, 10, 11, TS + 90], TS, content_frames=400)
    assert complete and segments == [(0, 90, [TS, 10, 11, TS + 90])]


def test_ties_go_to_the_first_language_as_before():
    assert _winner({"ro": ("", float("-inf")), "ru": ("", float("-inf"))}) == ("", "ro")
    assert _winner({"ro": ("a", -0.70), "ru": ("b", -0.67)}) == ("a", "ro")  # +0.1 for the home language


class Batched:
    batched = True

    def transcribe_all(self, pieces):
        return [(f"t{len(p)}", "ro", []) for p in pieces]


def test_batched_engines_get_every_piece_in_one_call():
    batches = [AudioBatch(i, i, i + 1, np.zeros(10 + i)) for i in range(3)]
    chunks = transcribe_batches(Batched(), batches)
    assert [(c.start, c.text) for c in chunks] == [(0, "t10"), (1, "t11"), (2, "t12")]


def test_a_relative_model_path_means_under_asr_llm(monkeypatch):
    from asr_llm.config import ASR_ROOT, Settings
    monkeypatch.setenv("MOM_ASR_MODEL_DIR", "models/whisper")
    assert Settings().asr_model_dir == ASR_ROOT / "models" / "whisper"


def test_the_second_language_waits_for_an_unsure_first_decode(monkeypatch):
    from asr_llm.asr_batched import BatchedDecoder
    from asr_llm.config import settings

    assert BatchedDecoder.first_pass(["ro", "ru", "en"]) == ["ro", "ru", "en"]   # off by default
    monkeypatch.setattr(settings, "asr_second_decode_below", -0.5)
    assert BatchedDecoder.first_pass(["ro", "ru", "en"]) == ["ro", "en"]
    assert BatchedDecoder.first_pass(["ru"]) == ["ru"]                            # a short piece's one language
