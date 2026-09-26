from asr_llm.ensemble import Word, combine


def words(text: str, t0: float = 0.0) -> list[Word]:
    return [Word(t0 + i * 0.4, t0 + (i + 1) * 0.4, w) for i, w in enumerate(text.split())]


def test_the_specialist_whose_output_is_real_vocabulary_wins():
    ro_speech = {
        "sped_ro": words("Pacientul a fost transferat la cardiologie ieri"),
        "gigaam_ru": words("Пациентул а фост трансферат ла кардиолоджие иери"),  # transliterated nonsense
    }
    out = combine(ro_speech)
    assert out["system"] == "sped_ro" and out["language"] == "ro"
    ru_speech = {
        "sped_ro": words("Nociu davlenie bîlo vosemdesiat na sorok"),
        "gigaam_ru": words("Ночью давление было восемьдесят на сорок"),
    }
    out = combine(ru_speech)
    assert out["system"] == "gigaam_ru" and out["text"] == "Ночью давление было восемьдесят на сорок"


def test_a_russian_aside_inside_a_romanian_sentence_is_taken_from_the_russian_system():
    hyps = {
        "sped_ro": words("Pacientul e stabil dar davlenie nizkoe dimineața"),
        "gigaam_ru": words("Пациентул е стабил дар давление низкое диминяца"),
    }
    out = combine(hyps)
    assert out["text"] == "Pacientul e stabil dar давление низкое dimineața"
    assert out["language"] == "ro+ru"


def test_english_is_recognised_from_a_multilingual_system():
    hyps = {
        "sped_ro": words("The board agreed"),  # a Romanian model writes what it hears
        "parakeet": words("The board agreed to renew the contract"),
    }
    out = combine(hyps)
    assert out["system"] == "parakeet" and out["language"] == "en"


def test_nothing_heard_gives_empty_text():
    assert combine({"sped_ro": [], "gigaam_ru": []})["text"] == ""
