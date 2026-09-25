"""Audio in: whole files via ffmpeg, or live blocks from the microphone.
Everything comes out as 16 kHz mono float32."""

import queue
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

from .neural import SR


def load(path) -> np.ndarray:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path.resolve()),
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
