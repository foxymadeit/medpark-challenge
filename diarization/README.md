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

The models it needs are in `models/` (two segmentation models, one per microphone
profile, and TitaNet-small, about 52 MB together), so nothing is downloaded at
runtime. The only command that touches the internet is `diarizer models fetch --all`,
and that just pulls the extra embedders we compare against.

## Use

```bash
diarizer live                          # talk; press Enter or Ctrl+C to finish
diarizer live --speakers 4             # hard cap on people; usually leave it out (see Measured)
diarizer file meeting.m4a --start-time 14:00:00
diarizer file meeting.m4a --mic far    # skip the microphone check (auto, close or far)
diarizer enroll "Dr. Popescu" --language ro        # optional: read the passage shown, about 25 s
diarizer enroll "Dr. Popescu" --language ru --add  # a second language for the same person
diarizer enroll "Dr. Popescu" --file clip.wav
```

`live` opens with a round of introductions: each person says their name and
role while the room check runs, you press Enter, and it lists the voices it
heard so you can type a name for each (or press Enter to keep Speaker N).
Then the meeting screen shows a scrolling voice waveform, who is talking now
(two names during overlap), talk time per person, and a log where a new voice
is marked `+ NEW VOICE` and a returning one `↺ BACK`, each turn with its start
and end. `--no-intro` skips the introductions; `--plain` (or piping the
output) prints plain lines instead of the screen.

Enrollment is optional. Without it people are Speaker 1, 2, 3; with it they
are named, and enroll warns when a new voice is close to someone already
enrolled.

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

## Microphone profiles

How far people sit from the microphone changes which models and settings do
best, so there are two profiles and a check that picks one:

| Profile | When | Segmentation | Voiceprints | Thresholds (assign, new, merge) |
|---|---|---|---|---|
| close | speakers near the mic: laptop in front of them, phone, headset | our fine-tuned `segmentation-ft.onnx` | raw TitaNet | 0.6, 0.4, 0.7 |
| far | one mic on the table, room audible | stock `segmentation-3.0.onnx` | AMI-trained projection | 0.40, 0.25, 0.90 |

`--mic auto` (the default) measures how far speech rises above the room's
background: at 15 dB or more it picks close, otherwise far. AMI table-mic
meetings measure 1 to 10 dB; the Medpark sample recording measures 9 dB and
gets the far profile. Live sessions listen for 10 s before they start
labelling. Picking the wrong profile costs 10 to 13 points of accuracy.

## How it works

Every 0.5 s, a segmentation model looks at the last 5 s of audio and
marks who is talking in each 17 ms frame. Each voice then gets a TitaNet
embedding from its clean frames (in the far profile, passed through a
projection trained on 38 AMI meetings that drops room sound). The tracker keeps an average and a few
voice prototypes per person, so someone switching from Romanian to Russian
keeps one label. It matches each new embedding to a known person or opens a
new one. Labels lag the audio by 1 s so the model has heard a bit past each
moment. When the session ends, every observation is scored again against
the final voiceprints before the minutes are written.

## Measured

Accuracy below is 100 minus DER (diarization error rate: missed speech,
false alarms and wrong labels, every 10 ms, no collar). Turn accuracy is the
share of reference turns that mostly went to the right person, which is how
often a line of the minutes gets the right name.

**Mixed Romanian / Russian / English meetings** (`eval/make_mix.py`): 24
meetings of 3 to 7 people built from voices no model here trained on,
including people switching between Romanian and Russian. Thresholds tuned on
6, scored on the other 18.

| Setup | Accuracy | Turn accuracy |
|---|---|---|
| **close profile** | **93.0%** (DER 7.0%) | **96.3%** |
| same, stock segmentation model | 90.1% | 94.6% |
| far profile on this clean speech | 80.2% | 81.6% |

**Long meetings with many people**: 4 meetings of 30 minutes with 11 to 14
people each (about 200 to 236 turns per meeting), built the same way.

| Setup | Accuracy | Turn accuracy |
|---|---|---|
| **close profile, head count unknown** | **93.6%** (DER 6.4%) | **95.9%** |
| same, `--speakers` set to the true count | 89.2% | 89.3% |

With the count left open it sometimes opens one or two extra speakers; forcing
the count merges real people instead, which costs more. Leave `--speakers` out.

**AMI far-field, one table mic, 4 speakers per meeting**, the harder case.
Thresholds tuned on 8 dev meetings, scored on 4 held-out test meetings
(ES2004a, IS1009a, TS3003a, EN2002a).

| Setup | Accuracy | Notes |
|---|---|---|
| **far profile** | **66.5%** (DER 33.5%) | the best public systems score about 78 to 85% here |
| close profile on this audio | 56.3% | why the microphone check matters |

What did not help: fine-tuning the TitaNet voice model (three runs on Kaggle
T4s, up to 4,585 voices of Russian, Romanian and English, including a
frozen-encoder low-learning-rate run) always separated unseen voices a
little worse than the original. The fine-tuned segmentation model helps
clean multilingual speech and costs about 3 points on far-field English,
which is why it is used only in the close profile. Details and code are in
`train/`.

Speed on a 2017 Intel i5 (2 cores, 8 GB): about 0.12 to 0.16x real time, so a
60-minute recording takes 7 to 10 minutes. `--step 1.0` halves the neural
work (0.06x) at a cost of about 3 points on the mixed set. Apple Silicon and
servers are several times faster.

## Evaluate and train

```bash
python -m eval.run_eval score --meetings ES2004a IS1009a TS3003a EN2002a
python -m eval.run_eval sweep --meetings ES2011a IS1008a     # threshold search on dev
python -m eval.embed_quality --meetings ES2011a IS1008a      # voiceprint separation vs ground truth
python -m train.fit_backend --data ../data/ami/train --dims 64
pytest
```

AMI audio and labels are in `../data/ami/` (see its README).
