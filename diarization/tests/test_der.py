import pytest

from eval.der import der, read_rttm


def test_perfect_hypothesis_scores_zero():
    ref = [("A", 0, 10), ("B", 10, 20)]
    hyp = [("x", 0, 10), ("y", 10, 20)]
    assert der(ref, hyp)["der"] == pytest.approx(0.0)


def test_label_names_do_not_matter_only_the_mapping():
    ref = [("A", 0, 10), ("B", 10, 20), ("A", 20, 30)]
    hyp = [("2", 0, 10), ("1", 10, 20), ("2", 20, 30)]
    assert der(ref, hyp)["der"] == pytest.approx(0.0)


def test_one_speaker_for_everything_costs_the_other_speakers_time():
    ref = [("A", 0, 10), ("B", 10, 20)]
    hyp = [("x", 0, 20)]
    r = der(ref, hyp)
    assert r["confusion"] == pytest.approx(0.5, abs=0.01)
    assert r["der"] == pytest.approx(0.5, abs=0.01)


def test_missed_and_false_alarm_speech():
    ref = [("A", 0, 10)]
    hyp = [("x", 5, 15)]
    r = der(ref, hyp)
    assert r["miss"] == pytest.approx(0.5, abs=0.01)
    assert r["false_alarm"] == pytest.approx(0.5, abs=0.01)


def test_read_rttm(tmp_path):
    p = tmp_path / "m.rttm"
    p.write_text("SPEAKER m 1 1.50 2.00 <NA> <NA> FEE005 <NA> <NA>\n")
    assert read_rttm(p) == [("FEE005", 1.5, 3.5)]


def test_turn_accuracy_counts_turns_given_to_the_right_person():
    from eval.der import der
    ref = [("A", 0.0, 2.0), ("B", 2.0, 4.0), ("A", 4.0, 6.0)]
    hyp = [("x", 0.0, 2.0), ("y", 2.0, 4.0), ("y", 4.0, 6.0)]  # last turn went to B's label
    assert abs(der(ref, hyp)["turn_accuracy"] - 2 / 3) < 1e-9
    assert der(ref, [("x", 0.0, 2.0), ("y", 2.0, 4.0), ("x", 4.0, 6.0)])["turn_accuracy"] == 1.0
