"""Uploaded audio is checked by its bytes, then decoded by ffprobe for its
real length. The client's file name and MIME type are never trusted."""

import json
import os
import re
import secrets
import shutil
import subprocess
from pathlib import Path

from fastapi import HTTPException, UploadFile

MAX_BYTES = 500 * 1024 * 1024
MAX_SECONDS = 3 * 3600
CHUNK = 1024 * 1024


def kind(head: bytes) -> str | None:
    """Container from the first bytes: wav, flac, mp3, mp4/m4a, webm, ogg."""
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"fLaC":
        return "flac"
    if head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "mp3"
    if head[4:8] == b"ftyp":
        return "m4a"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if head[:4] == b"OggS":
        return "ogg"
    return None


def duration(path: Path) -> float:
    exe = shutil.which("ffprobe")
    if not exe:
        raise HTTPException(503, "The audio decoder (ffprobe) is not installed on this server.")
    try:
        out = subprocess.run([exe, "-v", "error", "-protocol_whitelist", "file", "-show_entries", "format=duration", "-of", "json", str(path)],
                             capture_output=True, text=True, timeout=60, check=True).stdout
        return float(json.loads(out)["format"]["duration"])
    except (subprocess.SubprocessError, KeyError, ValueError, TypeError):
        pass
    # browser recordings (MediaRecorder WebM) carry no duration: decode to count it
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            err = subprocess.run([ffmpeg, "-nostdin", "-v", "info", "-protocol_whitelist", "file", "-i", str(path), "-f", "null", "-"],
                                 capture_output=True, text=True, timeout=600).stderr
            times = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", err)
            if times:
                h, m, s = times[-1]
                return int(h) * 3600 + int(m) * 60 + float(s)
        except subprocess.SubprocessError:
            pass
    raise HTTPException(422, "The file could not be decoded as audio.")


def save(upload: UploadFile, folder: Path, *, measure: bool = True) -> dict:
    """Stream the upload to a random name, checking size and type on the way."""
    folder.mkdir(parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    tmp = folder / f".upload-{secrets.token_hex(8)}"
    size, head = 0, b""
    try:
        with open(tmp, "xb") as f:
            os.chmod(tmp, 0o600)
            while chunk := upload.file.read(CHUNK):
                if not head:
                    head = chunk[:16]
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "The file is larger than 500 MB.")
                f.write(chunk)
        if size == 0:
            raise HTTPException(422, "The file is empty.")
        ext = kind(head)
        if ext is None:
            raise HTTPException(415, "Use WAV, MP3, M4A, FLAC, WebM or Ogg audio.")
        seconds = duration(tmp) if measure else 0.0
        if seconds > MAX_SECONDS:
            raise HTTPException(422, "The recording is longer than 3 hours.")
        if measure and seconds <= 0:
            raise HTTPException(422, "The file could not be decoded as audio.")
        final = folder / f"audio.{ext}"
        for old in folder.glob("audio.*"):
            old.unlink()
        tmp.replace(final)
        return {"path": final, "bytes": size, "seconds": round(seconds, 2), "kind": ext}
    finally:
        tmp.unlink(missing_ok=True)
