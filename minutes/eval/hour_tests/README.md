# One-hour tests

The challenge asks for under 15 minutes from upload to email for a 60-minute
recording on one 16 GB GPU. These two Kaggle jobs measure exactly that, on
public recordings, never on hospital audio and never on this laptop.

## The recordings (`data_kernel/`, CPU job `coflaz/liminal-hour-tests-data`)

Each is 60:00 of 16 kHz mono FLAC, published as the private Kaggle dataset
`coflaz/liminal-hour-tests` with a `manifest.json`.

| id | Language | Source | Licence | Reference |
|---|---|---|---|---|
| `icsi_60` | English | ICSI meeting Bmr005, headset mix ([download](https://groups.inf.ed.ac.uk/ami/icsi/download/)) | CC BY 4.0 | word transcript, speaker turns (RTTM) |
| `kremlin_60` | Russian | Meeting with Government members, 23 June 2026: mentorship for medical graduates ([kremlin.ru/events/president/news/80090](http://kremlin.ru/events/president/news/80090)) | CC BY 4.0 ([terms](http://en.kremlin.ru/about/copyrights)) | official transcript up to the last chapter that starts inside the hour (57.8 min); lightly edited, so CER is a ceiling |
| `md_parl_60` | Romanian and Russian | Moldovan Parliament plenary sessions ([YouTube playlist](https://www.youtube.com/playlist?list=PLAVLfBYYrdyTHyFw9wbJz8jrxR4LGOs1a)); up to 8 are scanned with Whisper-tiny language ID and the hour with the most minutes of both languages is kept | public broadcast, internal testing only | none: the stenograms are not reachable by machine |
| `rompar_60` | Romanian (Moldova, then Romania) | [ROMPAR](https://huggingface.co/datasets/avramandrei/rompar) test split, Moldovan utterances first, joined in record order | not stated; internal testing only | transcript and utterance times |

A source that fails is kept in the manifest with its error; the rest still
build.

What the first build found (26 September 2026, 20 minutes on a Kaggle CPU):

- `rompar_60`: 720 utterances, 643 Moldovan and 77 Romanian.
- `kremlin_60`: 12 speakers in the transcript up to 57.8 min.
- `md_parl_60`: the seven most recent plenary sessions on the playlist (92 to
  180 min each) held one minute of Russian between them, by Whisper-tiny's
  count. Plenaries no longer mix the two languages much, so this hour is
  effectively Moldovan Romanian with a trace of Russian. A real RO/RU
  code-switching hour still has to come from the challenge's own Medpark
  recordings or the team's scripted rounds, which stay off Kaggle.

## The timing (`speed_kernel/`, GPU job `coflaz/liminal-hour-speed`)

It clones `Coflazo-Branch` (diarization, minutes) and `samoilov-asr-llm`
(transcription) and runs the backend's own three commands on each hour:
transcription and diarization side by side, then `mom report` in RO, RU and
EN. It reports every stage's time, the total against 15 minutes, peak GPU and
RAM, CER and WER, the recogniser's language checks, DER on `icsi_60`, and the
minutes checks. Set `ASR_FETCH`, `ASR_ENV` and `MINUTES_MODEL` at the top to
the bake-off winners, then:

```bash
kaggle kernels push -p minutes/eval/hour_tests/speed_kernel
kaggle kernels output coflaz/liminal-hour-speed -p out/    # out/report.json
```

Expect about 20 minutes of setup (TeX, Ollama, Whisper and the minutes
model) and a 3-minute smoke test before the hours; these are estimates until
the first run reports.
