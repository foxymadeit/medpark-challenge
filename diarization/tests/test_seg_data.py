import numpy as np

from eval.make_mix import SR
from train.seg_data import room, synth_meetings, write_protocol


def test_room_echo_keeps_length_and_level():
    rng = np.random.default_rng(0)
    clip = rng.standard_normal(SR).astype(np.float32) * 0.1
    rir = np.exp(-np.arange(4000) / 800.0).astype(np.float32)
    wet = room(clip, rir)
    assert len(wet) == len(clip)
    assert abs(np.abs(wet).max() - np.abs(clip).max()) < 1e-5


def test_synthetic_meetings_have_three_to_six_people_and_valid_turns():
    rng = np.random.default_rng(1)
    voices = {f"cv_ro_{i}": [rng.standard_normal(SR * 3).astype(np.float32) * 0.1] * 3 for i in range(8)}
    noise = [rng.standard_normal(SR * 2).astype(np.float32) * 0.01]
    for audio, ref in synth_meetings(voices, 3, rng, rirs=[np.ones(10, np.float32)], noises=noise, minutes=0.5):
        assert 3 <= len({w for w, _, _ in ref}) <= 6
        assert all(e > s for _, s, e in ref) and ref[-1][2] <= len(audio) / SR + 1e-6


def test_protocol_files_describe_every_meeting(tmp_path):
    wav = tmp_path / "m.wav"
    wav.write_bytes(b"")
    db = write_protocol(tmp_path / "proto", {"train": [("m1", wav, [("a", 0.0, 1.5), ("b", 1.2, 3.0)], (0.0, 3.0))],
                                              "development": [("m2", wav, [("a", 0.0, 2.0)], (0.0, 2.0))]})
    text = db.read_text()
    assert "MOM: " in text and "far:" in text and "development:" in text
    assert (tmp_path / "proto" / "train.rttm").read_text().count("SPEAKER m1") == 2
    assert (tmp_path / "proto" / "wav" / "m1.wav").is_symlink()
