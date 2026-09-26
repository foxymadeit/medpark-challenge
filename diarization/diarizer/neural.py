"""The two neural models: who is talking right now (segmentation) and
what their voice sounds like (speaker embedding). Both run on CPU via ONNX."""

import numpy as np
import onnxruntime as ort
import sherpa_onnx

SR = 16000

# pyannote segmentation-3.0: 7 powerset classes over 3 local speakers,
# at most 2 at once. Order: none, {0}, {1}, {2}, {0,1}, {0,2}, {1,2}.
_POWERSET = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
                      [1, 1, 0], [1, 0, 1], [0, 1, 1]], dtype=bool)


class Segmenter:
    hop = 270          # samples between output frames (16.875 ms)
    receptive = 991    # samples each frame looks at

    def __init__(self, path, threads: int = 1):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        self._sess = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])

    def __call__(self, audio: np.ndarray) -> np.ndarray:
        """Per-frame activity of up to 3 local speakers, shape (frames, 3)."""
        x = np.asarray(audio, dtype=np.float32)[None, None, :]
        logp = self._sess.run(None, {"x": x})[0][0]
        return _POWERSET[np.argmax(logp, axis=-1)]

    def frame_span(self, i):
        """Sample range [a, b) that frame i stands for; consecutive frames tile."""
        center = i * self.hop + self.receptive // 2
        return center - self.hop // 2, center + self.hop - self.hop // 2


class Embedder:
    def __init__(self, path, threads: int = 1, backend=None):
        cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(path), num_threads=threads)
        if not cfg.validate():
            raise ValueError(f"bad embedding model config for {path}")
        self._ex = sherpa_onnx.SpeakerEmbeddingExtractor(cfg)
        self.backend = backend
        self.dim = backend.proj.shape[1] if backend is not None else self._ex.dim

    def __call__(self, samples: np.ndarray) -> np.ndarray:
        stream = self._ex.create_stream()
        stream.accept_waveform(sample_rate=SR, waveform=np.asarray(samples, dtype=np.float32))
        stream.input_finished()
        v = np.asarray(self._ex.compute(stream), dtype=np.float32)
        v = v / (np.linalg.norm(v) + 1e-9)  # the projection was trained on unit vectors
        return self.backend(v) if self.backend is not None else v
