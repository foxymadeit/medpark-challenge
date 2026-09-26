from asr_llm.correct import correct_segments, correct_text
from asr_llm.schemas import SpeechSegment


def test_misheard_terms_snap_to_the_dictionary_in_their_own_language():
    assert correct_text("Pacientul a avut infarct miocradic ieri.", "ro")[0] == "Pacientul a avut infarct miocardic ieri."
    assert correct_text("Are hipertensiune arterală.", "ro")[0] == "Are hipertensiune arterială."
    assert correct_text("У пациента пневмания.", "ru")[0] == "У пациента пневмония."


def test_inflected_and_ordinary_words_are_left_alone():
    for text, lang in [
        ("S-a făcut ecografia și electrocardiograma.", "ro"),       # articles, not errors
        ("Da, bine, facem mâine dimineață la ora nouă.", "ro"),
        ("Пациент в реанимации, давление стабильное, завтра выписка.", "ru"),
        ("Лечение пневманией не начинали.", "ru"),                    # case ending must not be overwritten
        ("The board agreed to renew the contract this week.", "en"),
    ]:
        assert correct_text(text, lang) == (text, [])


def test_a_russian_term_never_lands_in_a_romanian_sentence():
    assert correct_text("Pacientul are пневмания.", "ro") == ("Pacientul are пневмания.", [])


def test_every_change_is_logged_with_its_time():
    seg = SpeechSegment(start=12.5, end=15.0, text="Diagnostic: infarct miocradic.", language="ro")
    log = correct_segments([seg])
    assert seg.text == "Diagnostic: infarct miocardic."
    assert log == [{"start": 12.5, "language": "ro", "before": "infarct miocradic", "after": "infarct miocardic", "score": 94.1}]


def test_word_merge_swaps_in_a_confident_russian_run_and_nothing_else():
    from asr_llm.asr import merge_words
    from asr_llm.schemas import Hypothesis

    ro = Hypothesis(language="ro", text="", words=[(0.0, 0.4, "Pacientul", 0.95), (0.4, 0.8, "e", 0.9),
                                                   (0.8, 1.2, "ne", 0.2), (1.2, 1.6, "stabil", 0.25)])
    ru = Hypothesis(language="ru", text="", words=[(0.0, 0.4, "Пациентул", 0.3), (0.4, 0.8, "е", 0.2),
                                                   (0.8, 1.2, "не", 0.9), (1.2, 1.6, "стабилен", 0.85)])
    assert merge_words(ro, [ru]) == ("Pacientul e не стабилен", ["ru"])
    weak = ru.model_copy(update={"words": [(w[0], w[1], w[2], 0.3) for w in ru.words]})
    assert merge_words(ro, [weak]) == ("Pacientul e ne stabil", [])


def test_a_term_approved_on_site_is_corrected_too(tmp_path, monkeypatch):
    import json

    from asr_llm import correct, glossary

    site = tmp_path / "site_glossary.json"
    site.write_text(json.dumps({"aligned": [{"source": "site", "ro": "zorvatinib", "heard": "zorvatenib"}]}))
    monkeypatch.setenv("LIMINAL_SITE_GLOSSARY", str(site))
    glossary.load_glossary.cache_clear(), correct._terms.cache_clear()
    try:
        assert correct_text("Pacientul primește zorvatenib.", "ro")[0] == "Pacientul primește zorvatinib."
    finally:
        monkeypatch.delenv("LIMINAL_SITE_GLOSSARY")
        glossary.load_glossary.cache_clear(), correct._terms.cache_clear()
    assert correct_text("Pacientul primește zorvatenib.", "ro")[0] == "Pacientul primește zorvatenib."
