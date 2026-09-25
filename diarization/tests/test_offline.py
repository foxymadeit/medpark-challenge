"""End to end with the network switched off: any socket use fails the test."""

import json
import socket
import subprocess
from pathlib import Path

import pytest

from diarizer import models
from diarizer.cli import main

MEDPARK = Path(__file__).resolve().parents[2] / "data" / "Medpark_audio.m4a"


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("diarizer tried to open a network connection")
    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.mark.skipif(not MEDPARK.exists(), reason="Medpark sample not present")
def test_file_mode_runs_offline_and_writes_turns(tmp_path, no_network):
    try:
        models.model_path(models.SEGMENTATION)
        models.embedder_path(models.DEFAULT_EMBEDDER)
    except FileNotFoundError:
        pytest.skip("models not downloaded")
    clip = tmp_path / "clip.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-t", "20", "-i", str(MEDPARK),
                    "-ac", "1", "-ar", "16000", str(clip)], check=True)
    main(["file", str(clip), "--out", str(tmp_path / "out"), "--start-time", "14:00:00", "--no-voices"])
    session = json.loads(next((tmp_path / "out").glob("*.json")).read_text())
    assert session["turns"], "expected at least one turn in 20 s of meeting audio"
    for t in session["turns"]:
        assert t["start"] < t["end"]
        assert t["start_clock"].startswith("14:00:")
