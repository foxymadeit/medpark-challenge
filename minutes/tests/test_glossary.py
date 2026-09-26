import time

from mom.glossary import terms_for
from mom.schemas import Fact
from mom.write import write_body


def test_infarct_in_romanian_gives_the_russian_and_english_terms():
    rows = terms_for(["Pacientul cu infarct miocardic acut va face RMN."], "ru")
    ami = next(r for r in rows if r["en"] == "Acute myocardial infarction")
    assert ami["ru"] == "Острый инфаркт миокарда" and ami["matched"] == "Infarct miocardic acut"
    assert any(r["en"] == "MRI" for r in rows)


def test_unrelated_text_matches_nothing():
    assert terms_for(["Vremea a fost frumoasă astăzi, am băut o cafea."], "en") == []


def test_two_hundred_facts_take_under_50_ms():
    texts = ["Se aprobă internarea pacientului în ATI după CT, cu suspiciune de insuficiență cardiacă."] * 200
    terms_for(texts, "en")   # first call reads the table
    t = time.perf_counter()
    terms_for(texts, "en")
    assert time.perf_counter() - t < 0.05


class Recorder:
    def chat(self, system, user, **k):
        self.user = user
        return ""


def test_the_writer_is_told_the_standard_terms():
    facts = [Fact("T1", "topic", "Cazul din salonul 12", ["L0001"], quote="x"),
             Fact("N1", "note", "Pacientul are infarct miocardic acut.", ["L0001"], quote="x", topic="T1")]
    llm = Recorder()
    write_body(llm, facts, "en", {"N1": "infarct miocardic acut"})
    assert "Infarct miocardic acut → Acute myocardial infarction" in llm.user


def test_a_term_approved_on_site_reaches_the_writer(tmp_path, monkeypatch):
    import json

    from mom import glossary

    site = tmp_path / "site_glossary.json"
    site.write_text(json.dumps({"aligned": [{"source": "site", "ro": "zorvatinib", "heard": "zorvatenib"}]}))
    monkeypatch.setenv("LIMINAL_SITE_GLOSSARY", str(site))
    glossary._table.cache_clear()
    try:
        rows = terms_for(["Pacientul primește zorvatinib de mâine."], "ro")
        assert any(r["source"] == "site" and r["matched"] == "zorvatinib" for r in rows)
    finally:
        monkeypatch.delenv("LIMINAL_SITE_GLOSSARY")
        glossary._table.cache_clear()
    assert not any(r["source"] == "site" for r in terms_for(["Pacientul primește zorvatinib de mâine."], "ro"))
