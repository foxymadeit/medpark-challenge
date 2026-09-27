"""Model files. Runtime code only reads local files.

`fetch()` is the one function in this package that opens a network
connection. It runs once, at setup time, while the laptop is online. The
default models are also committed to the repo, so a fresh clone works with
no network at all.
"""

import hashlib
import io
import os
import tarfile
import urllib.request
from pathlib import Path

MODELS_DIR = Path(os.environ.get("DIARIZER_MODELS") or Path(__file__).resolve().parent.parent / "models")

_RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
SEGMENTATION = os.environ.get("DIARIZER_SEGMENTATION", "segmentation-3.0.onnx")
_SEG_SOURCE = (f"{_RELEASES}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2",
               "sherpa-onnx-pyannote-segmentation-3-0/model.onnx",
               "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079")

EMBEDDERS = {
    "resnet34": ("wespeaker_en_voxceleb_resnet34_LM.onnx",
                 "e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012"),
    "titanet-small": ("nemo_en_titanet_small.onnx",
                      "ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e"),
    "campp": ("wespeaker_en_voxceleb_CAM++_LM.onnx",
              "e197af7e9d473030cf486b3124149a19bf37014d0e4485e4c70c483b0ec10cb2"),
}
# Picked on AMI ground truth (same person across a whole meeting). TitaNet-small
# separated speakers far better than ResNet34 or CAM++ (d-prime 1.9-6.2 vs
# 0.15-1.3) and is the fastest of the three on CPU.
DEFAULT_EMBEDDER = "titanet-small"
# Fine-tuned on Kaggle (train/kaggle/). Nothing to download: they ship in models/.
LOCAL_ONLY = {"titanet-small-ft", "titanet-small-multi"}

# Learned projection applied after the embedder (train/fit_backend.py, trained
# on 38 AMI training meetings, 120 speakers). Loaded automatically when present.
BACKENDS = {"titanet-small": "titanet-small.backend.d64.npz"}

# Cosine thresholds per embedder, in the space the tracker actually sees (after
# the backend when one exists). Tuned on 8 AMI dev meetings with eval/run_eval.py.
THRESHOLDS = {
    "campp": {"assign": 0.55, "new": 0.45, "merge": 0.75},
    "resnet34": {"assign": 0.55, "new": 0.45, "merge": 0.75},
    "titanet-small": {"assign": 0.40, "new": 0.25, "merge": 0.90},
}


def model_path(filename: str) -> Path:
    p = MODELS_DIR / filename
    if not p.is_file():
        raise FileNotFoundError(
            f"{p} is missing. Run `diarizer models fetch` once while online, "
            "or copy the models/ folder from a teammate.")
    return p


def embedder_path(name: str) -> Path:
    if name not in EMBEDDERS:
        raise ValueError(f"unknown embedder {name!r}; choose from {', '.join(EMBEDDERS)}")
    return model_path(EMBEDDERS[name][0])


def backend_path(embedder: str):
    """Path of the embedder's trained backend, or None when it has none."""
    name = BACKENDS.get(embedder)
    p = MODELS_DIR / name if name else None
    return p if p and p.is_file() else None


def fetch(embedders=(DEFAULT_EMBEDDER,), log=print) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    seg = MODELS_DIR / SEGMENTATION
    if not _ok(seg, _SEG_SOURCE[2]):
        log(f"downloading {SEGMENTATION}")
        with tarfile.open(fileobj=io.BytesIO(_download(_SEG_SOURCE[0])), mode="r:bz2") as tar:
            data = tar.extractfile(_SEG_SOURCE[1]).read()
        _save(seg, data, _SEG_SOURCE[2])
    for name in embedders:
        if name in LOCAL_ONLY:
            continue
        filename, sha = EMBEDDERS[name]
        dest = MODELS_DIR / filename
        if not _ok(dest, sha):
            log(f"downloading {filename}")
            _save(dest, _download(f"{_RELEASES}/speaker-recongition-models/{filename}"), sha)
    log(f"models ready in {MODELS_DIR}")


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 (fixed https URLs above)
        return r.read()


def _save(dest: Path, data: bytes, sha: str) -> None:
    got = hashlib.sha256(data).hexdigest()
    if got != sha:
        raise RuntimeError(f"checksum mismatch for {dest.name}: got {got}, expected {sha}")
    dest.write_bytes(data)


def _ok(path: Path, sha: str) -> bool:
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha
