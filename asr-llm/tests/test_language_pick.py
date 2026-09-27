import numpy as np

from asr_llm.asr import _is_hallucination, pick_language

from test_asr_lid import SR, FakeWhisper, engine

# Cases from hour test 3 (one T4): English lines of the ICSI hour and the mock boards that came out
# Romanian or Russian, and the Moldovan Romanian close call the home bias exists for.


def test_a_russian_decode_written_in_latin_letters_is_not_russian():
    assert pick_language({"ro": ("", float("-inf")), "ru": ("The order tomorrow.", -0.59), "en": ("The order tomorrow.", -0.64)}) == ("The order tomorrow.", "en")


def test_a_romanian_or_english_decode_written_in_cyrillic_is_dropped():
    assert pick_language({"ro": ("Каждые две недели.", -0.2), "ru": ("Каждые две недели.", -0.4)})[1] == "ru"
    assert pick_language({"ru": ("Да.", -0.5), "en": ("Да.", -0.1)})[1] == "ru"


def test_a_decode_that_kept_the_english_words_is_english():
    # forced Romanian, Whisper wrote the English anyway: same words as the English decode
    got = pick_language({"ro": ("Survey is on the 20th of...", -0.30), "ru": ("Опрос двадцатого.", -0.84), "en": ("Survey is on the 20th of...", -0.38)})
    assert got == ("Survey is on the 20th of...", "en")


def test_the_home_bias_only_settles_romanian_against_russian():
    assert pick_language({"ro": ("Mulțumesc.", -0.70), "ru": ("Спасибо.", -0.67)})[1] == "ro"        # Moldovan close call
    assert pick_language({"ro": ("Mâine la 9.", -0.46), "ru": ("Завтра в 9.", -0.84), "en": ("Tomorrow at 9.", -0.38)})[1] == "en"
    assert pick_language({"ro": ("Da, bine.", -0.35), "en": ("Yes, fine.", -0.48)})[1] == "ro"          # Romanian still wins on its own score


def test_digits_fit_any_script_and_ties_go_to_the_first_language():
    assert pick_language({"ro": ("4-5", -0.5), "ru": ("4-5", -0.5)}) == ("4-5", "ro")
    assert pick_language({"ro": ("", float("-inf")), "ru": ("", float("-inf"))}) == ("", "ro")
    assert pick_language({"ro": ("Da.", -0.4), "en": ("Da.", -0.4)})[1] == "ro"


def test_the_one_at_a_time_path_uses_the_same_pick():
    # Mac (MLX) and single-utterance decoding go through transcribe_batch
    fake = FakeWhisper([("en", 0.6), ("ro", 0.3)], {"ro": -0.46, "ru": -0.84, "en": -0.38},
                       texts={"ro": "Mâine la 9.", "ru": "Завтра в 9.", "en": "Tomorrow at 9."})
    assert engine(fake).transcribe_batch(np.zeros(SR * 3))[:2] == ("Tomorrow at 9.", "en")


def test_the_long_subscribe_credit_is_a_hallucination():
    assert _is_hallucination("Nu uitați să dați like, să lăsați un comentariu și să distribuiți acest material video pe alte rețele sociale.")
    assert _is_hallucination("să vă pregătesc să vă abonați la canalul meu.")
    assert not _is_hallucination("Nu uitați să trimiteți lista până vineri.")
