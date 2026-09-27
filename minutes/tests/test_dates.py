import pytest

from mom.dates import resolve

MEETING = "2026-09-24"  # a Thursday


@pytest.mark.parametrize("phrase,expected", [
    ("până vineri", "2026-09-25"),
    ("до пятницы", "2026-09-25"),
    ("by Friday", "2026-09-25"),
    ("luni", "2026-09-28"),
    ("в понедельник", "2026-09-28"),
    ("on Monday", "2026-09-28"),
    ("joi", "2026-10-01"),              # same weekday means next week's
    ("mâine", "2026-09-25"),
    ("завтра", "2026-09-25"),
    ("tomorrow", "2026-09-25"),
    ("în 3 zile", "2026-09-27"),
    ("через 2 недели", "2026-10-08"),
    ("in two weeks", "2026-10-08"),
    ("până la sfârșitul lunii", "2026-09-30"),
    ("до конца месяца", "2026-09-30"),
    ("by the end of the month", "2026-09-30"),
    ("до конца недели", "2026-09-25"),
    ("30.09.2026", "2026-09-30"),
    ("pe 5 octombrie", "2026-10-05"),
    ("до 5 октября", "2026-10-05"),
    ("by 5 October", "2026-10-05"),
    ("October 5th", "2026-10-05"),
    ("2026-10-12", "2026-10-12"),
])
def test_deadlines_resolve_against_the_meeting_date(phrase, expected):
    assert resolve(phrase, MEETING) == expected


@pytest.mark.parametrize("phrase", ["săptămâna viitoare", "на следующей неделе", "next week", "cât mai curând", "asap", "", "soon"])
def test_vague_deadlines_are_not_guessed(phrase):
    assert resolve(phrase, MEETING) == ""


def test_without_a_meeting_date_only_explicit_dates_resolve():
    assert resolve("până vineri", "") == ""
    assert resolve("30.09.2026", "") == "2026-09-30"


def test_today_and_within_n_days_in_three_languages():
    from mom.dates import resolve
    d = "2026-09-24"
    assert resolve("Actualizez graficul și îl public azi.", d) == "2026-09-24"
    assert resolve("сегодня до вечера", d) == "2026-09-24"
    assert resolve("I'll send it today", d) == "2026-09-24"
    assert resolve("în termen de 7 zile", d) == "2026-10-01"
    assert resolve("в течение 3 дней", d) == "2026-09-27"
