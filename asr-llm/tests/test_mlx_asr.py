import sys
from types import ModuleType, SimpleNamespace

import numpy as np

SR = 16_000


def _fake_mlx(monkeypatch, texts, scores, probs):
    """mlx, mlx_whisper and its submodules, just enough for the adapter."""
    core = ModuleType("mlx.core")
    core.float16 = "float16"
    mlx = ModuleType("mlx")
    mlx.core = core
    model = SimpleNamespace(dims=SimpleNamespace(n_mels=128))
    mw = ModuleType("mlx_whisper")
    mw.transcribe = lambda audio, language, **_: {"segments": [
        {"start": 0.0, "end": 2.0, "text": texts[language], "avg_logprob": scores[language], "no_speech_prob": 0.0}]}
    tr = ModuleType("mlx_whisper.transcribe")
    tr.ModelHolder = SimpleNamespace(get_model=lambda path, dtype: model)
    audio = ModuleType("mlx_whisper.audio")
    audio.N_FRAMES = 3000
    mel = SimpleNamespace(astype=lambda dtype: "mel")
    audio.log_mel_spectrogram = lambda samples, n_mels: mel
    audio.pad_or_trim = lambda m, n, axis: m
    dec = ModuleType("mlx_whisper.decoding")
    dec.detect_language = lambda model, mel: (None, [probs])
    for name, mod in {"mlx": mlx, "mlx.core": core, "mlx_whisper": mw, "mlx_whisper.transcribe": tr,
                      "mlx_whisper.audio": audio, "mlx_whisper.decoding": dec}.items():
        monkeypatch.setitem(sys.modules, name, mod)


def test_mlx_engine_keeps_the_whisper_pick(monkeypatch, tmp_path):
    # LID says Russian with confidence, as it does on Moldovan Romanian; the ro decode scores better and wins.
    _fake_mlx(monkeypatch, {"ro": "Pacientul patul opt.", "ru": "Пациент палата восемь."},
              {"ro": -0.4, "ru": -0.7}, {"ru": 0.9, "ro": 0.08, "lt": 0.02})
    from asr_llm.config import settings
    from asr_llm.mlx_asr import MlxWhisperAsr

    monkeypatch.setattr(settings, "mlx_model_dir", tmp_path)
    asr = MlxWhisperAsr()
    text, lang, hyps = asr.transcribe_batch(np.zeros(SR * 3, np.float32))
    assert (text, lang, asr.device) == ("Pacientul patul opt.", "ro", "mlx")
    assert [h.language for h in hyps] == ["ro", "ru"]
