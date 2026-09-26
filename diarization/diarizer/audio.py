"""Audio in: whole files via ffmpeg, or live blocks from the microphone.
Everything comes out as 16 kHz mono float32."""

import queue
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

from .neural import SR


# First bytes of the containers we accept. Anything else is refused before
# ffmpeg sees it: playlists (m3u8) and concat lists would make ffmpeg open
# other local files or network addresses, which breaks the offline promise.
_MAGIC = (b"RIFF", b"FORM", b"fLaC", b"OggS", b"ID3", b"\x1a\x45\xdf\xa3", b"caff", b"#!AMR",
          b"\x30\x26\xb2\x75")
_MP4_BOXES = (b"ftyp", b"moov", b"mdat", b"wide", b"free")


def check_audio_header(path) -> None:
    with open(path, "rb") as f:
        head = f.read(12)
    ok = (head.startswith(_MAGIC) or head[4:8] in _MP4_BOXES
          or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0))  # MPEG audio / ADTS AAC frame sync
    if not ok:
        raise ValueError(f"{path} is not a supported audio file (WAV, MP3, M4A, FLAC, OGG, WebM, AAC)")


def load(path) -> np.ndarray:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    check_audio_header(path)
    if shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file", "-i", str(path.resolve()),
               "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
        out = subprocess.run(cmd, capture_output=True, check=False)
        if out.returncode != 0 and not out.stdout:
            raise RuntimeError(f"ffmpeg could not decode {path}: {out.stderr.decode()[-300:]}")
        return np.frombuffer(out.stdout, dtype=np.float32).copy()
    return _load_wav(path)


def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        if w.getframerate() != SR or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise RuntimeError(f"{path}: without ffmpeg only 16 kHz mono 16-bit WAV is supported")
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


def mic_blocks(block_s: float = 0.1, device=None):
    """Yield (samples, stream_start_epoch). The epoch is read from the local
    clock when the first block arrives; later times are that plus sample count."""
    import time

    import sounddevice as sd

    q: queue.Queue = queue.Queue()

    def callback(indata, frames, t, status):
        q.put(indata[:, 0].copy())

    with sd.InputStream(samplerate=SR, channels=1, dtype="float32", device=device,
                        blocksize=int(block_s * SR), callback=callback):
        first = q.get()
        start = time.time() - len(first) / SR
        yield first, start
        while True:
            yield q.get(), start
