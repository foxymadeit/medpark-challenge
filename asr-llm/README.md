# ASR + local LLM (reference hardware)

Target: **one 16 GB GPU**, or **CPU 32 GB RAM**. Runtime: **no internet**.

Diarization and n8n are other people's slices.

## How the process runs

```
audio (or a ready transcript JSON)
        │
        ▼
 1. ffmpeg → 16 kHz mono
 2. Silero VAD → utterances           ← cut at every ≥300 ms pause, ≤15 s
    (+ diarizer turns: cut again where the speaker changes)
 3. decode every utterance as ro AND ru ← Whisper LID says ru 0.9 on plain Moldovan RO
    (+ en when LID's top pick is en); keep the higher avg_logprob,
    ro gets +0.1 as the meeting's main language
    clip < 1.5 s → reuse previous language
    drop known subtitle hallucinations ("Продолжение следует…")
 4. faster-whisper large-v3           ← NO glossary, NO hotwords
 5. unload Whisper
        │
        ▼
 6. retrieve ~24 glossary rows        ← numpy search over medical_ro_ru_en.json
    that look like this transcript
        │
        ▼
 7. local LLM (GGUF), per 10-min window ← summary + action items + term normalize
    windows merged in Python (dedupe), one short call for title/summary
 8. JSON minutes
```

Whisper never sees the dictionary. The LLM sees a **subset** retrieved from the frozen JSON. Nothing is trained on the Medpark sample.

Two ways in:

- **Full:** audio file → steps 1–8 (needs Whisper weights + GGUF, CUDA if available).
- **Skip ASR:** `--from-transcript transcript_v2.json` → steps 6–8 (needs GGUF only). Use this for the Kaggle v2 text.

`--preview-glossary` stops after step 6: prints the retrieved table, no LLM.

## Models (copy in by hand, or one-time fetch while you still have internet)

```
asr-llm/models/whisper/                         # Systran faster-whisper large-v3
asr-llm/models/llm/qwen2.5-7b-instruct-q4_k_m.gguf
```

```bash
python scripts/fetch_qwen.py    # Qwen/Qwen2.5-7B-Instruct-GGUF, q4_k_m, ~4.7 GB
```

## Canary check (Kaggle T4, not the Mac)

Whisper v2 stays the frozen baseline. Canary-1B-v2 is a second ASR pass on the
same audio. Weights download on Kaggle (Internet ON, GPU T4). Paste
`scripts/kaggle_canary_bench.py` into one cell. It writes
`/kaggle/working/transcript_canary.json` in the same shape as the Whisper bench.
Canary is told `source_lang=ro` (transcribe, not translate); Russian and English
stretches may lose to Whisper.

## Run

```bash
cd asr-llm
pip install -e ".[asr,llm,dev]"

# See which terms the retriever picks (no GPU LLM required)
python -m asr_llm.cli --from-transcript ~/Downloads/transcript_v2.json --preview-glossary

# Minutes from the Kaggle v2 transcript
python -m asr_llm.cli --from-transcript ~/Downloads/transcript_v2.json \
  --meeting-type medical --out /tmp/mom.json

# Full local audio path (slow on M4 CPU, fine on NVIDIA 16 GB)
python -m asr_llm.cli ../data/Medpark_audio.m4a --meeting-type medical --out /tmp/mom.json
```

## Why the ASR works this way

Measured on `data/Medpark_audio.m4a` (11:42):

| Run | What went wrong |
|---|---|
| Whisper large-v3, auto language per 15 s chunk | 59 % of letters Cyrillic in a mostly Romanian meeting: `Ело фост … ку инфаркт миокарди` (RO written as RU), plus RO/RU decoded as Lithuanian |
| Canary-1B-v2 forced to `ro` | Romanian fine, Russian mangled, loops "Eu cum." on the last 30 s |
| old energy VAD | kept 198 s of 702 s: its threshold was the median loudness, which in a busy meeting *is* speech |
| Whisper forced to `ru` on Romanian speech | it **translates**: "dreapta și stânga" → "и правая, и левая" — a fluent lie, lower avg_logprob than the `ro` decode |

First 113 s, 14 utterances, ro vs ru decode: LID picked `ru` on 12 of them (0.54–0.94) though
nearly all are Romanian. avg_logprob picked the right language on 10/14; the 4 misses were
within 0.06, which the +0.1 home bias flips.

Tuning knobs (env `MOM_*`): `HOME_LANGUAGE` / `HOME_BIAS`, `ASR_ALWAYS_DECODE`, `MIN_LID_S`,
`VAD_MIN_SILENCE_MS`, `ASR_MODEL_DIR` (turbo for CPU-only / speed), `LLM_WINDOW_S`.

## Measuring ASR

```bash
python -m asr_llm.score transcript.json                        # LID / script checks, no gold needed
python -m asr_llm.score transcript.json --gold data/gold_0-181s.txt --window 181   # + CER/WER, term hits
```

`script_mismatch` counts `ro` lines written in Cyrillic (and `ru` in Latin). The gold file is
the first 3 min corrected by hand by someone who speaks RO and RU. Judge every ASR change by it.

GPU check on Kaggle (T4, Internet ON only for the fetch):

```bash
git clone -b samoilov-asr-llm https://github.com/foxymadeit/medpark-challenge && cd medpark-challenge/asr-llm
pip install -e ".[asr]" && python scripts/fetch_whisper.py large-v3
MOM_ASR_COMPUTE_TYPE=int8_float16 python -m asr_llm.cli ../data/Medpark_audio.m4a --skip-llm --out transcript.json
python -m asr_llm.score transcript.json
```

## Mixed-language sentences: LLM fusion (optional, off by default)

Every utterance keeps all its decodes (`segments[].hypotheses`). With `MOM_FUSION=single`, one
model looks at the **unclear** utterances only (ro/ru scores within `FUSE_MARGIN`, or best below
`FUSE_FLOOR`), 15 per call. Its answer must be built from hypothesis words (≥85 %) and may not
swap wholesale to a clearly worse-scored decode; otherwise the acoustic winner stays. A
forced-Russian decode of Romanian speech reads fluently, so fluency is not evidence.

A multi-model debate (every model, every sentence, two rounds) was tried and removed: it took
81 min for 11.7 min of audio, and on the hand-corrected gold it scored CER 0.46 against 0.47
for no fusion at all.

Models come from GGUF files or a local Ollama:

```bash
brew install ollama && brew services start ollama          # listens on 127.0.0.1 only
ollama pull qwen3.5:9b

# compare on the same transcript (hypotheses from the Kaggle bench or a local run)
MOM_LLM_MODEL=ollama:qwen3.5:9b python -m asr_llm.cli --from-transcript t.json --fusion single --fuse-only --out single.json
python -m asr_llm.score single.json --gold data/gold_0-181s.txt --window 181
```

## Trilingual medical dictionary

`scripts/build_glossary.py` (dev time only) turns the 2,050 Harvard terms plus
`data/icu_terms_en.txt` into RO/RU/EN rows with definitions: Wikidata labels for
entities with a MeSH/UMLS/ICD id first, then Qwen2.5-32B on Kaggle for the rest,
checked by back-translation (`back_ok`). Runtime only reads the merged JSON. The
fusion and minutes prompts get the ~24 rows that match the text, the best five with
a short definition.

## With diarization

```bash
diarizer file meeting.m4a --out sessions/x          # Coflazo-Branch
python -m asr_llm.cli meeting.m4a --diarization sessions/x/meeting.json --out mom.json
```

`POST /minutes` takes the same file as an optional `diarization` form field.

## Tests

```bash
pytest
```
