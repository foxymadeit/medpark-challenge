from mom.anonymize import anonymize_text, initials


def test_initials_keep_every_given_name_and_the_surname():
    assert initials("Ana Maria Petrova") == "A.M.P."
    assert initials("Ион Русу") == "И.Р."


def test_known_patient_names_become_initials_everywhere():
    patients = [{"name": "Ana Petrova"}]
    assert anonymize_text("Pacienta Ana Petrova, 67 ani. Petrova a fost operată.", patients) == "Pacienta A.P., 67 ani. A.P. a fost operată."


def test_names_after_patient_words_are_caught_even_if_the_model_missed_them():
    assert anonymize_text("Пациентка Мария Иванова поступила вчера.", []) == "Пациентка М.И. поступила вчера."
    assert anonymize_text("The patient John Smith was discharged.", []) == "The patient J.S. was discharged."
    assert anonymize_text("Pacientul Ion Rusu, salonul 4.", []) == "Pacientul I.R., salonul 4."


def test_staff_names_are_left_alone():
    assert anonymize_text("Dr. Igor Rusu a prezentat cazul.", []) == "Dr. Igor Rusu a prezentat cazul."
