import json

from mom.normalize import load_transcript


def test_plain_text_with_times_and_speakers(tmp_path):
    p = tmp_path / "t.txt"
    p.write_text("[00:00:03] Speaker 1: Bună ziua.\n[00:00:07] Ana Popescu: Începem ședința.\n", encoding="utf-8")
    lines = load_transcript(p)
    assert [(l.id, l.start, l.speaker, l.text) for l in lines] == [("L0001", 3.0, "Speaker 1", "Bună ziua."), ("L0002", 7.0, "Ana Popescu", "Începem ședința.")]


def test_plain_paragraphs_without_any_markup(tmp_path):
    p = tmp_path / "t.txt"
    p.write_text("Primul rând.\n\nAl doilea rând.\n", encoding="utf-8")
    assert [l.text for l in load_transcript(p)] == ["Primul rând.", "Al doilea rând."]


def test_srt_and_vtt(tmp_path):
    srt = tmp_path / "t.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:04,500\nIgor Rusu: Propun RMN.\n\n2\n00:00:05,000 --> 00:00:06,000\nDe acord.\n", encoding="utf-8")
    lines = load_transcript(srt)
    assert (lines[0].start, lines[0].end, lines[0].speaker, lines[0].text) == (1.0, 4.5, "Igor Rusu", "Propun RMN.")
    vtt = tmp_path / "t.vtt"
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Ana Popescu>Aprobăm.\n", encoding="utf-8")
    assert load_transcript(vtt)[0].speaker == "Ana Popescu"


def test_whisper_json_shapes(tmp_path):
    shapes = {
        "openai": {"segments": [{"start": 1.0, "end": 2.0, "text": " Salut."}]},
        "faster": [{"start": 1.0, "end": 2.0, "text": "Salut."}],
        "cpp": {"transcription": [{"offsets": {"from": 1000, "to": 2000}, "text": "Salut."}]},
        "attach": {"lines": [{"start": 1.0, "end": 2.0, "speaker": "Speaker 2", "text": "Salut."}]},
    }
    for name, data in shapes.items():
        p = tmp_path / f"{name}.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        line = load_transcript(p)[0]
        assert (line.start, line.end, line.text) == (1.0, 2.0, "Salut."), name


def test_speakers_come_from_a_diarizer_session_when_the_transcript_has_none(tmp_path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps({"segments": [{"start": 0.5, "end": 3.0, "text": "Propun RMN."}, {"start": 3.2, "end": 5.0, "text": "De acord."}]}))
    s = tmp_path / "s.json"
    s.write_text(json.dumps({"turns": [{"speaker": "Igor Rusu", "start": 0.0, "end": 3.1}, {"speaker": "Speaker 2", "start": 3.1, "end": 6.0}]}))
    assert [l.speaker for l in load_transcript(t, s)] == ["Igor Rusu", "Speaker 2"]
