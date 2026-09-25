from __future__ import annotations

from pathlib import Path


def require_local_path(path: Path, what: str) -> Path:
    """Runtime must use files already on disk. No download, no remote URLs."""
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(
            f"{what} not found at {resolved}. "
            "Copy the model here during setup, then run offline."
        )
    return resolved


def pick_device(explicit: str) -> str:
    if explicit in {"cuda", "cpu"}:
        return explicit
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"
