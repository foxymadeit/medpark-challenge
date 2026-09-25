from diarizer.timeline import Timeline, Turn


def spans(turns):
    return [(t.speaker, round(t.start, 2), round(t.end, 2)) for t in turns]


def test_short_pauses_stay_inside_one_turn():
    tl = Timeline(min_gap=0.5)
    tl.add(1, 0.0, 0.5)
    tl.add(1, 0.5, 1.0)
    tl.add(1, 1.2, 2.0)
    assert spans(tl.finish()) == [(1, 0.0, 2.0)]


def test_long_pause_splits_turns():
    tl = Timeline(min_gap=0.5)
    tl.add(1, 0.0, 1.0)
    tl.add(1, 2.0, 3.0)
    assert spans(tl.finish()) == [(1, 0.0, 1.0), (1, 2.0, 3.0)]


def test_alternating_speakers():
    tl = Timeline()
    tl.add(1, 0.0, 1.0)
    tl.add(2, 1.0, 2.0)
    tl.add(1, 2.0, 3.0)
    assert spans(tl.finish()) == [(1, 0.0, 1.0), (2, 1.0, 2.0), (1, 2.0, 3.0)]


def test_blips_shorter_than_min_dur_are_dropped():
    tl = Timeline(min_dur=0.3)
    tl.add(1, 0.0, 2.0)
    tl.add(2, 1.0, 1.1)
    assert spans(tl.finish()) == [(1, 0.0, 2.0)]


def test_overlapping_speech_keeps_both_speakers():
    tl = Timeline()
    tl.add(1, 0.0, 2.0)
    tl.add(2, 1.5, 3.0)
    assert spans(tl.finish()) == [(1, 0.0, 2.0), (2, 1.5, 3.0)]


def test_live_events_start_then_end():
    tl = Timeline(min_gap=0.5, min_dur=0.3)
    assert tl.add(2, 5.0, 5.2) == []  # too short to announce yet
    assert tl.add(2, 5.2, 5.5) == [("start", 2, 5.0)]
    assert tl.add(2, 5.5, 6.0) == []
    assert tl.close_idle(now=6.4) == []  # still inside the pause allowance
    assert tl.close_idle(now=6.6) == [("end", Turn(2, 5.0, 6.0))]


def test_relabel_merges_split_speaker_back():
    tl = Timeline(min_gap=0.5)
    tl.add(1, 0.0, 1.0)
    tl.add(3, 1.1, 2.0)
    tl.relabel({3: 1})
    assert spans(tl.finish()) == [(1, 0.0, 2.0)]
