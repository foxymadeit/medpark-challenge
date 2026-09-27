import os
import stat

import numpy as np
import pytest

from diarizer import audio, export, voices
from diarizer.tracker import SpeakerTracker


def test_playlists_and_non_audio_files_are_refused(tmp_path):
    for name, body in (("list.m3u8", b"#EXTM3U\n#EXTINF:1,\nfile:///etc/passwd\n"),
                       ("c.txt", b"ffconcat version 1.0\nfile '/etc/hosts'\n"),
                       ("fake.wav", b"<html>not audio</html>")):
        p = tmp_path / name
        p.write_bytes(body)
        with pytest.raises(ValueError, match="not a supported audio file"):
            audio.load(p)


def test_real_audio_headers_pass(tmp_path):
    for body in (b"RIFF\x00\x00\x00\x00WAVEfmt ", b"fLaC\x00\x00", b"OggS\x00\x02", b"ID3\x04\x00",
                 b"\x00\x00\x00\x20ftypM4A ", b"\xff\xfb\x90\x00", b"\x1a\x45\xdf\xa3\x01"):
        p = tmp_path / "a.bin"
        p.write_bytes(body + b"\x00" * 64)
        audio.check_audio_header(p)  # no exception


def test_voiceprints_and_sessions_are_private(tmp_path, monkeypatch):
    monkeypatch.setattr(voices, "VOICES_DIR", tmp_path / "voices")
    path = voices.save_voice("Ana", "titanet-small", [np.ones(4)])
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700
    session = {"session_start": "2026-09-26T10:00:00", "source": "x", "model": "m", "speakers": {},
               "turns": [{"speaker": "Speaker 1", "start_clock": "a", "end_clock": "b", "start": 0.0, "end": 1.0}]}
    for p in export.write_all(tmp_path / "sess", session, uri="s"):
        assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(tmp_path / "sess").st_mode) == 0o700


def _old_sims(t, embs):
    return np.array([[t.similarity(e, s) for s in t._speakers] for e in embs]).reshape(len(embs), len(t._speakers))


def test_vectorised_similarity_matches_the_per_speaker_loop():
    rng = np.random.default_rng(3)
    t = SpeakerTracker()
    for k in range(40):
        t.enroll(f"p{k}", [rng.standard_normal(16) for _ in range(int(rng.integers(1, 9)))])
    embs = [rng.standard_normal(16) for _ in range(3)]
    unit = [e / np.linalg.norm(e) for e in embs]
    assert np.allclose(t._sims(unit), _old_sims(t, embs), atol=1e-6)


def test_replay_plays_a_recording_like_a_microphone(tmp_path):
    import itertools

    from scipy.io import wavfile

    from diarizer.audio import replay_blocks
    wav = tmp_path / "r.wav"
    wavfile.write(wav, 16000, (np.ones(16000 * 3 // 10) * 0.1).astype(np.float32))
    blocks = [b for b, _ in itertools.islice(replay_blocks(wav, block_s=0.1), 5)]
    assert all(len(b) == 1600 for b in blocks)
    assert blocks[0].max() > 0 and blocks[-1].max() == 0  # the recording, then silence
