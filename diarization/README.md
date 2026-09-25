# diarizer

Who spoke when, for Secure MOM. It runs on a laptop with the network off.

`diarizer live` listens to the microphone and gives each new voice the next
label (Speaker 1, Speaker 2, ...). A returning voice gets its old label back.
`diarizer file` runs the same engine over a recording. Both write every turn
as `speaker, start, end` on the local clock.

```
19:49:32.680  ▶ Speaker 1
19:49:34.654  ■ Speaker 1  19:49:32.680 → 19:49:34.654  (1.97 s)
```

## Setup

```bash
cd diarization
uv venv --python 3.11 && uv pip install -e '.[dev]'
```

The two models it needs are in `models/` (the segmentation model and TitaNet-small,
about 46 MB together), so nothing is downloaded at runtime. The only
command that touches the internet is `diarizer models fetch --all`, and that
just pulls the extra embedders we compare against.

## Use

```bash
diarizer live                          # talk; press Enter or Ctrl+C to finish
diarizer live --speakers 4             # at most 4 people (optional)
diarizer file meeting.m4a --start-time 14:00:00
diarizer enroll "Dr. Popescu"          # record ~20 s so the name shows up instead of "Speaker N"
diarizer enroll "Dr. Popescu" --file clip.wav
```

The number of speakers doesn't need to be known in advance, and there is no
upper limit. The segmenter separates up to 3 people inside any 5 s window
(2 talking at once). Over a whole meeting the tracker keeps adding
speakers as new voices appear. A test covers 100 people.

Outputs land in `sessions/<start time>/`:

- `<id>.json` for the pipeline: `turns: [{speaker, start_clock, end_clock, start, end}]`
  plus talk time per speaker. `start`/`end` are seconds from the session start.
- `<id>.rttm` is the standard diarization format, used for scoring.
- `<id>.csv` is for people.

To put names on a Whisper transcript of the same recording:

```bash
diarizer attach sessions/20260925-141000/20260925-141000.json whisper.json
```

Each line goes to the speaker whose turns overlap it most. If Whisper was run
with word timestamps, a line two people share is split where the voice
changes. It reads openai-whisper JSON, a faster-whisper segment list, or
whisper.cpp `-oj` output, and writes `<session>.transcript.json` with
`speaker, start, end, start_clock, end_clock, text` per line.

## How it works

Every 0.5 s, pyannote segmentation-3.0 looks at the last 5 s of audio and
marks who is talking in each 17 ms frame. Each voice then gets a TitaNet
embedding from its clean frames, passed through a projection trained on 38 AMI
meetings (120 speakers) that keeps what tells voices apart and drops room sound. The tracker keeps an average and a few
voice prototypes per person, so someone switching from Romanian to Russian
keeps one label. It matches each new embedding to a known person or opens a
new one. Labels lag the audio by 1 s so the model has heard a bit past each
moment. When the session ends, every observation is scored again against
the final voiceprints before the minutes are written.

## Measured (AMI far-field table mic, 4 speakers per meeting, 1 s latency)

| Set | DER | Speaker count right | Notes |
|---|---|---|---|
| AMI dev, 8 meetings | 27.7% | 5 of 8 | thresholds tuned here |
| AMI test, 4 meetings (ES2004a, IS1009a, TS3003a, EN2002a) | **33.5%** | 1 of 4 exact, 2 over | held out, never tuned on |

The test number is with the trained projection. Without it the same test set scores 38.2%, and
with the first thresholds (tuned on 2 meetings) it scored 41.4%. The largest remaining error
is missed speech (about 14%), quiet far-field talk the segmenter does not mark as speech.

Speed on a 2017 Intel i5 (2 cores, 8 GB): about 0.15-0.25x real time, so a
60-minute recording takes 10-15 minutes. Apple Silicon and servers are
several times faster.

## Evaluate and train

```bash
python -m eval.run_eval score --meetings ES2004a IS1009a TS3003a EN2002a
python -m eval.run_eval sweep --meetings ES2011a IS1008a     # threshold search on dev
python -m eval.embed_quality --meetings ES2011a IS1008a      # voiceprint separation vs ground truth
python -m train.fit_backend --data ../data/ami/train --dims 64
pytest
```

AMI audio and labels are in `../data/ami/` (see its README).
