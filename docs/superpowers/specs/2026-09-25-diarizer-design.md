# Secure MOM: live + file speaker diarization (`diarizer`)

> Status: implemented. Current behaviour and measured numbers are in
> [diarization/README.md](../../../diarization/README.md). This spec is kept as written.

## Context

The team is building Secure MOM for the Medpark GigaHack challenge. It is an on-premise pipeline
that turns hospital meeting audio (Romanian/Russian/English code-switching, medical vocabulary)
into Minutes of Meeting with action items, owners and deadlines, with zero network calls at runtime.

**My slice is speaker diarization ("who spoke when").** It scores as a bonus, and it lets the LLM
attribute each action item to the person who took it.

What the user asked for:
- A terminal CLI that **listens live to the mic** and labels voices as they appear:
  me → `Speaker 1`, a new voice → `Speaker 2`, me again → `Speaker 1`, a third voice → `Speaker 3`.
- Works **without knowing how many speakers** there are. It optionally accepts a count
  (e.g. `--speakers 4`) or **pre-enrolled voices**.
- **Language independent:** the same person is recognized whether they speak RO, RU or EN.
- A **clock:** every turn is stored as `speaker, start, end` on the local wall clock (no Wi-Fi),
  and finalize prints e.g. `Speaker 1  14:02:03.120 → 14:02:10.880`.
- The fastest possible detection, on any machine of the reference class: 16 GB M4, **this dev box
  (Intel i5-7360U, 8 GB, macOS 13, where PyTorch no longer ships)**, a server with one 16 GB GPU,
  or a CPU-only 32 GB server.
- A simple test environment.
- Every good update gets a commit and a push to `Coflazo-Branch`, with human-sounding notes (voice
  and humanizer passes), authored as Coflazo, with no AI trailers.

Decisions made with the user:
- **Python orchestrating C++ engines** (sherpa-onnx / ONNX Runtime). No torch at runtime.
- **Live mic mode + file mode.** File mode feeds the team's 60-minute upload pipeline.
- **Real fine-tuning** of the speaker model, as a gated phase after a measured baseline.
- Test audio: `/Users/pc/Downloads/Medpark_audio.m4a` (11.7 min, ALAC 48 kHz stereo, 56 MB,
  the only file in the organizers' Drive folder). The organizers handed it to every team, and the
  user said to **commit it**. It lives at `data/Medpark_audio.m4a` on both `main` and
  `Coflazo-Branch`. It still never goes to a cloud GPU for fine-tuning; that uses public data only.
- Research tooling: Playwright MCP failed to connect this session and Firecrawl returns 401, so
  we use WebSearch/WebFetch until one of them is back. The user prefers Playwright over Firecrawl.

Process: superpowers spine (brainstorming → this plan → TDD). karpathy-coder and ponytail are
always on. algorithms (clustering), security-audit (before shipping), and voice + humanizer
(commit notes) are used where they apply.

## Research findings that shape the design

- **sherpa-onnx** (k2-fsa, Apache-2.0) has a C++ core with Python wheels for macOS, Linux and
  Windows. It provides Silero VAD, a speaker-embedding extractor, an embedding manager and offline
  diarization (pyannote segmentation-3.0 + embeddings + clustering). The models are **ungated
  GitHub-release downloads**, so no Hugging Face token is needed.
- **diart** (juanmc2005) is the proven *streaming* algorithm: a rolling 5 s window with a
  0.5 s step, the pyannote segmentation model giving up to 3 local speakers per window, one
  embedding per local speaker, then incremental clustering against global centroids. Distinct
  local speakers are forced onto distinct global speakers, and a new speaker is created when the
  embedding is too far from every centroid. We **re-implement that algorithm (~200 lines) on top
  of ONNX models** instead of depending on diart, which is torch-based and pinned to pyannote.
- **whosaid** (sblattj, MIT) is offline and file-only, with Apple-Silicon-only transcription.
  Its diarization runs on sherpa-onnx with TitaNet-small. It gives us measured cosine statistics:
  same speaker mean 0.90 (lowest 10%: 0.72), different speakers mean 0.25 (highest 10%: 0.45).
  Starting cut-offs: 0.58 to group turns, 0.70 to assign a turn to an enrolled voice, 0.85 to
  merge two groups. **Its lesson:** comparing each new turn against a single earlier turn keeps
  creating new speakers. Compare against **group averages** and add a **merge pass**.
- **Fine-tuning data (CC0):** Common Voice RU 26.0 (292 h, 3,744 speakers, via Mozilla Data
  Collective, which needs a free account), Common Voice RO (same place), and VoxPopuli RO (89 h,
  164 speakers, `speaker_id` labels, on Hugging Face). Published research favors adapter or
  low-learning-rate fine-tuning with a new classifier head.
- Delay is set by how much audio we wait for (0.5 to 1 s), not by compute. Per 0.5 s step,
  segmentation plus up to 3 embeddings is roughly tens of milliseconds on CPU.

Three background research tracks (streaming tools, the sherpa-onnx API, the embedding-model
comparison) are still running. Anything they turn up goes into the Phase 0 checks below.

## Architecture

New self-contained package in `diarization/` (repo root stays untouched):

```
diarization/
  pyproject.toml        numpy, sherpa-onnx, onnxruntime, sounddevice; dev: pytest
  README.md             usage, measured speed and accuracy, hardware notes
  diarizer/
    cli.py              argparse: models fetch | enroll | live | file
    models.py           dev-time download with sha256 pins; runtime loads local files only
    audio.py            mic stream (sounddevice, 16 kHz mono) + file decode (ffmpeg subprocess, list args)
    segmenter.py        pyannote seg-3.0 ONNX on a window → per-frame activity of ≤3 local speakers
    embedder.py         thin wrapper over sherpa_onnx.SpeakerEmbeddingExtractor
    tracker.py          speaker memory: centroids, new-speaker gate, merge, enrolled anchors, --speakers cap
    engine.py           rolling-window loop: segmenter → embedder → tracker → frame labels
    timeline.py         frame labels → turns (speaker, start, end), smoothing, wall-clock mapping
    export.py           JSON / RTTM / CSV + the printed summary
    voices.py           enrollment store (voices/<name>.npy + model id)
  tests/                pytest, synthetic embeddings, no models needed
  eval/                 make_mix.py, der.py, run_eval.py
  finetune/             phase 3
data/                   Medpark_audio.m4a (committed) + team/ recordings (gitignored)
```

### Live algorithm (engine.py + tracker.py)
1. Mic → 16 kHz mono ring buffer. Clock: `t0_wall = time.time()` at the first callback, and each
   sample time is `t0_wall + n/16000`. The sample count doesn't drift relative to the audio, and
   the wall anchor comes from the local RTC.
2. Every `--step` (0.5 s default), run segmentation on the last `--window` (5 s default): frame
   activity for ≤3 local speakers.
3. For each local speaker active long enough, gather the samples where **only** that speaker is
   active. At ≥1.0 s of clean audio, embed it with sherpa-onnx.
4. Tracker assigns local speakers to global speakers using the best one-to-one assignment by
   cosine (brute force over ≤3 × K, no scipy).
   - Best similarity ≥ `assign` → that speaker, and update its centroid (running mean, capped weight).
   - Below `new` everywhere and embedded from ≥1.0 s of clean speech → **new Speaker N**.
   - In between → nearest speaker, with no centroid update (avoids pollution).
   - Enrolled voices are pre-seeded named centroids, and a turn has to reach 0.70 to take that name.
   - `--speakers N`: after N speakers exist, always assign to the nearest.
   - Merge pass: two centroids above the merge cut-off combine into the older ID.
5. The timeline merges frame labels into turns, prints `▶ Speaker 2  14:02:03.1` when a turn
   starts and `■ Speaker 2  14:02:03.1 → 14:02:07.9 (4.8 s)` when it ends.
6. Ctrl+C or `q` finalizes: a summary table (speaker, start, end per turn, plus total talk time
   per speaker), and `session.json` / `.rttm` / `.csv` are written to `--out`.

### File mode
The same engine is fed from the decoded file (faster than real time). This gives exactly the same
output format and the same code path as live mode, so tests cover both. Timestamps are offsets
from the file start, plus an absolute time if `--start-time` or the file's creation time is known.
The phase 2 option of a global re-cluster at finalize is only kept if eval shows it helps.

### Integration contract for the team
`session.json`: `{session_start, model, speakers: {id: {name, talk_time}}, turns: [{speaker, start, end}]}`,
plus standard RTTM. The Whisper owner assigns each ASR segment to the speaker with the largest
time overlap.

### Offline guarantee
Only `diarizer models fetch` touches the network (dev time). Runtime code has no HTTP imports,
and a pytest blocks `socket` and runs file mode end to end.

## Phases

### Phase 0: setup and checks (~30 min)
1. **Seed `main` and the branch (the user's explicit request, done first):**
   - copy `/Users/pc/Downloads/Medpark_audio.m4a` → `data/Medpark_audio.m4a` (56 MB, under
     GitHub's 100 MB per-file limit);
   - commit on `Coflazo-Branch` with the Harvard dictionary CSV/JSON and scraper already there;
   - `git push origin Coflazo-Branch` and then `git push origin Coflazo-Branch:main`, which
     creates `main` with the same content (scraper, Harvard terms, audio). Check both branches
     with `gh api`;
   - the repo's default branch setting stays as it is (not our repo; the user didn't ask).
   - `.gitignore`: `models/`, `sessions/`, `.venv/`, `__pycache__/`, and team recordings under
     `data/team/`. After this, all diarizer work stays on `Coflazo-Branch` only.
2. `uv` venv on Python 3.11. Install sherpa-onnx, onnxruntime, sounddevice and numpy. **Check
   that wheels exist for macOS x86_64**, and if onnxruntime has dropped them, pin the last version
   that ships them.
3. `diarizer models fetch`: seg-3.0 ONNX plus 3 candidate embedders (WeSpeaker ResNet34-LM,
   TitaNet-small, 3D-Speaker CAM++), with sha256 pinned.
4. Smoke test: sherpa-onnx offline diarization on the Medpark file. Record runtime and speaker count.
5. Commit the design doc to `docs/superpowers/specs/2026-09-25-diarizer-design.md` and push.

### Phase 1: core, test-first (~4 to 6 h)
1. `tracker.py` + tests (synthetic embeddings): new-speaker creation, re-identifying a returning
   speaker, `--speakers` cap, enrolled anchors, merge pass, one-to-one assignment.
2. `timeline.py` + `export.py` + tests: turn building, minimum-duration smoothing, clock mapping,
   JSON/RTTM/CSV round-trip.
3. `segmenter.py`, `embedder.py`, `engine.py`: an integration test on a generated two-voice mix.
4. `cli.py`: `live`, `file`, `enroll`. Manual live test on this laptop's mic with 2 to 3 people.
5. Commit and push after each green milestone.

### Phase 2: test environment + calibration (~3 to 4 h)
1. `eval/make_mix.py`: builds multi-speaker mixes with exact ground-truth RTTM from single-speaker
   clips, with random turn order, short gaps and some overlap.
2. `eval/der.py`: DER (miss + false alarm + confusion, 0.25 s collar, best speaker mapping),
   speaker-count error, and how fast a new speaker gets detected.
3. `eval/run_eval.py`: file mode and **simulated live** (the file streamed through the live
   engine), for each candidate embedder.
4. Data:
   - (a) teammates each record about 60 s of reading in RO, RU and EN, which gives a
     **cross-lingual same-speaker test** and clean mixes;
   - (b) about 5 min of Medpark audio hand-labeled (RTTM) by listening.
5. Pick the default embedder and thresholds by measurement. Report DER, count error, delay and
   the real-time factor on this Intel i5 (worst case) in the README.

### Phase 3: fine-tuning (gated on the Phase 2 baseline, ~1 to 2 days)
1. **Backend adaptation (CPU, hours):** fit a whitening/LDA transform on in-domain embeddings
   (VoxPopuli RO, CV RO, CV RU) and apply it before cosine. Cheap, and often a solid gain.
2. **Network fine-tune (GPU):** WeSpeaker recipe starting from the chosen model. Data: CV RU
   plus CV RO plus VoxPopuli RO, with a VoxCeleb slice kept in so the model doesn't forget what
   it knows. New AAM-softmax head, low learning rate or adapters, MUSAN/RIR augmentation. Run it
   on a free Kaggle or Colab T4, or a teammate's GPU, with **public data only**. Export to ONNX
   with sherpa-onnx metadata.
3. Ship it only if cross-lingual EER **and** Phase 2 DER beat the baseline. Otherwise keep the
   baseline and document the result.

### Before shipping
security-audit focused review (subprocess, file paths, model download pinning), the
socket-blocked test, and a code-reviewer pass. Then commit and push.

## Verification

- `uv run pytest diarization/tests`: all green, including the socket-blocked end-to-end test.
- `diarizer file data/Medpark_audio.m4a --out sessions/medpark`: finishes well under real time
  on the Intel i5, and prints turns plus a summary.
- `diarizer live`: I speak (Speaker 1), a second person speaks (Speaker 2), I speak again
  (back to Speaker 1), a third person speaks (Speaker 3). Labels appear within about 1 s of
  a speaker change, and Ctrl+C prints `speaker, start, end` for every turn with wall-clock times.
- Same person switching RO → RU → EN keeps one label (the cross-lingual eval set).
- `python eval/run_eval.py`: a DER / count / delay table for each embedder. The chosen default
  and its numbers go in the README.
- Network off (Wi-Fi disabled): file and live modes both run end to end.
- `git log -1 --format='%an <%ae>'` = Coflazo on every commit, and `git push` to `Coflazo-Branch`.

## What the research settled (added after approval)

- Default embedder: WeSpeaker ResNet34-LM (`wespeaker_en_voxceleb_resnet34_LM.onnx`, 26.5 MB,
  CC-BY-4.0). Of the ready-made checkpoints it had the lowest error on the 40-language
  TidyVoice/L-Proto trials (3.23% EER). CAM++ (4.06%) and ECAPA (4.15%) lose more accuracy when
  the language changes. TitaNet-small and CAM++ stay in the eval as challengers.
- The same speaker forms separate clusters for each language. The tracker therefore keeps up to
  8 voice prototypes per speaker, not a single centroid, and scores a new embedding against the
  best of them. Nuisance Attribute Projection estimated from our own RO/RU/EN recordings is the
  first Phase 3 step.
- sherpa-onnx 1.13.8 has no streaming diarization API (maintainer, issue #2072), so live mode
  runs the pyannote segmentation-3.0 ONNX directly: input `[N,1,T]` at 16 kHz, output
  `[N,frames,7]` powerset log-probabilities, 270-sample frame hop, 991-sample receptive field.
  Class order: none, {0}, {1}, {2}, {0,1}, {0,2}, {1,2}.
- onnxruntime dropped Intel Mac wheels after 1.23.2; `pyproject.toml` pins it there for
  `darwin/x86_64` only.
- The two default models (segmentation 5.7 MB, MIT; ResNet34-LM 26.5 MB, CC-BY-4.0) are
  committed under `diarization/models/` so a fresh clone runs with no network at all.
- Watch list: NVIDIA Nemotron-3-Diarization (released 2026-09-23, 8-speaker cap, no enrollment,
  strong DER). A possible optional backend later, not the default.
