from asr_llm.retrieve import llm_glossary_for, retrieve_terms


def test_retrieve_finds_terms_mentioned_in_text():
    hits = retrieve_terms(
        "Pacientul are insuficiență cardiacă și fluconazol pentru candida.",
        k=24,
    )
    blob = " ".join(f"{h.ro} {h.ru} {h.en}" for h in hits).lower()
    assert "pacient" in blob or "heart" in blob or "insuficien" in blob or "flucon" in blob


def test_unused_rare_terms_are_not_forced():
    hits = retrieve_terms("The budget meeting starts at noon.", k=8)
    blob = " ".join(h.en.lower() for h in hits)
    assert "cholera" not in blob
    assert "parkinson" not in blob


def test_llm_glossary_includes_hospital_ops_and_guardrail():
    table = llm_glossary_for("BIPAP saturatie 92 hidronefroza", k=16)
    assert "Do not add unused terms" in table
    assert "pacient" in table.lower()
    assert "ro | ru | en" in table
