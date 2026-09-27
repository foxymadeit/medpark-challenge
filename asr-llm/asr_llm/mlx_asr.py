"""Whisper large-v3 on the Apple GPU (MLX), for Macs, where faster-whisper runs on the CPU only.

WhisperAsr's per-utterance logic is kept whole (forced RO and RU decodes, LID for a third
language, the pick, the silence and hallucination filters); only the model underneath is
swapped for an adapter with faster-whisper's two calls, transcribe and detect_language.
mlx-whisper has no beam search: decoding is greedy, with its temperature fallback.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from .asr import WhisperAsr
from .config import settings
from .local import require_local_path


class _MlxModel:
    def __init__(self, path: str) -> None:
        import mlx.core as mx
        from mlx_whisper.transcribe import ModelHolder

        self.path = path
        self.model = ModelHolder.get_model(path, mx.float16)  # the instance mlx_whisper.transcribe reuses

    def transcribe(self, samples: np.ndarray, language: str, **_) -> tuple[list, None]:
        import mlx_whisper

        out = mlx_whisper.transcribe(samples, path_or_hf_repo=self.path, language=language,
                                     condition_on_previous_text=False, word_timestamps=settings.cs_merge)
        return [SimpleNamespace(start=s["start"], end=s["end"], text=s["text"], avg_logprob=s["avg_logprob"],
                                no_speech_prob=s["no_speech_prob"],
                                words=[SimpleNamespace(**w) for w in s.get("words", [])]) for s in out["segments"]], None

    def detect_language(self, samples: np.ndarray) -> tuple[str, float, list[tuple[str, float]]]:
        import mlx.core as mx
        from mlx_whisper.audio import N_FRAMES, log_mel_spectrogram, pad_or_trim
        from mlx_whisper.decoding import detect_language

        mel = pad_or_trim(log_mel_spectrogram(samples, n_mels=self.model.dims.n_mels), N_FRAMES, axis=-2)
        _, probs = detect_language(self.model, mel.astype(mx.float16))
        probs = probs[0] if isinstance(probs, list) else probs
        ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[0][0], ranked[0][1], ranked


class MlxWhisperAsr(WhisperAsr):
    def __init__(self) -> None:  # not WhisperAsr.__init__: no faster-whisper model
        self.model_id = str(require_local_path(settings.mlx_model_dir, "MLX Whisper model dir"))
        self.device = "mlx"
        self.batched = False  # one utterance per call; the Apple GPU does the work inside it
        self._model = _MlxModel(self.model_id)
