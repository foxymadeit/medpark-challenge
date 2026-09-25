from diarizer.attach import attach, load_segments

TURNS = [
    {"speaker": "Speaker 1", "start": 0.0, "end": 5.0},
    {"speaker": "Speaker 2", "start": 5.0, "end": 12.0},
    {"speaker": "Speaker 1", "start": 30.0, "end": 34.0},
]


def test_segment_inside_a_turn_gets_that_speaker():
    out = attach([{"start": 1.0, "end": 3.0, "text": " Good morning."}], TURNS)
    assert out == [{"speaker": "Speaker 1", "start": 1.0, "end": 3.0, "text": "Good morning."}]


def test_segment_across_two_turns_goes_to_the_larger_overlap():
    out = attach([{"start": 4.0, "end": 9.0, "text": "Mostly the second voice."}], TURNS)
    assert out[0]["speaker"] == "Speaker 2"


def test_word_times_split_a_segment_where_the_speaker_changes():
    seg = {"start": 3.0, "end": 7.0, "text": " Agreed. Next item?", "words": [
        {"start": 3.0, "end": 3.6, "word": " Agreed."},
        {"start": 5.4, "end": 5.9, "word": " Next"},
        {"start": 5.9, "end": 6.4, "word": " item?"},
    ]}
    assert attach([seg], TURNS) == [
        {"speaker": "Speaker 1", "start": 3.0, "end": 3.6, "text": "Agreed."},
        {"speaker": "Speaker 2", "start": 5.4, "end": 6.4, "text": "Next item?"},
    ]


def test_speech_the_diarizer_missed_takes_the_nearest_turn_within_the_gap():
    near = attach([{"start": 13.0, "end": 14.0, "text": "trailing"}], TURNS, max_gap=2.0)
    far = attach([{"start": 20.0, "end": 21.0, "text": "nobody near"}], TURNS, max_gap=2.0)
    assert near[0]["speaker"] == "Speaker 2"
    assert far[0]["speaker"] is None


def test_reads_the_three_whisper_json_shapes():
    openai = {"text": "hi", "segments": [{"id": 0, "start": 0.5, "end": 1.5, "text": " hi"}]}
    bare = [{"start": 0.5, "end": 1.5, "text": " hi"}]
    cpp = {"transcription": [{"offsets": {"from": 500, "to": 1500}, "text": " hi"}]}
    for obj in (openai, bare, cpp):
        assert load_segments(obj) == [{"start": 0.5, "end": 1.5, "text": " hi"}]
