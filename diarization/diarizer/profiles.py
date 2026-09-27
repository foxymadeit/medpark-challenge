"""Two ways of hearing a room, and a check that picks between them.

close: the speaker is near the microphone (laptop in front of them, phone,
headset). The fine-tuned segmentation model and raw voiceprints do best:
93.0% on 18 held-out Romanian/Russian/English meetings, the right name on
96.3% of turns.

far: a microphone in the middle of the table, with the room audible. The
stock segmentation model and the AMI-trained projection do best: 66.5% on
the AMI far-field test meetings, where the fine-tuned model drops to 56%.

The check compares how loud speech is with the room in between (the speech
detector decides which is which). AMI table-mic meetings measure 1 to 10 dB
and the Medpark sample recording 8.8 dB; clean close speech is far above 15.
"""

import numpy as np

PROFILES = {
    "close": {"segmentation": "segmentation-ft.onnx", "backend": False, "assign": 0.6, "new": 0.4, "merge": 0.7},
    "far": {"segmentation": "segmentation-3.0.onnx", "backend": True, "assign": 0.40, "new": 0.25, "merge": 0.90},
}
CLOSE_ABOVE_DB = 15.0


def speech_to_background_db(audio, segmenter, seconds: float = 120.0, sr: int = 16000) -> float:
    """Median speech-frame power over median background-frame power, in dB,
    from the first `seconds` of audio in 5 s windows. NaN when either is missing."""
    x = np.asarray(audio, dtype=np.float32)[: int(seconds * sr)]
    speech, background = [], []
    for w0 in range(0, max(len(x) - 5 * sr, 0) + 1, 5 * sr):
        win = x[w0:w0 + 5 * sr]
        if len(win) < segmenter.receptive:
            break
        for i, on in enumerate(segmenter(win).any(axis=1)):
            a, b = segmenter.frame_span(i)
            (speech if on else background).append(float(np.mean(win[a:b] ** 2)) + 1e-12)
    if not speech or not background:
        return float("nan")
    return float(10 * np.log10(np.median(speech) / np.median(background)))


def pick(db: float) -> str:
    return "close" if db >= CLOSE_ABOVE_DB else "far"  # NaN compares False: the harder case
