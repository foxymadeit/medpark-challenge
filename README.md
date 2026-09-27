# Secure MOM: offline diarization and minutes

Secure MOM turns a hospital meeting into minutes: a summary, the decisions,
and the action items with owners and deadlines, emailed to the right team.
We are building it for the Medpark International Hospital challenge at
DeepTech GigaHack 2026 (Chișinău), where the rule is that audio and
transcripts never leave the hospital.

This branch holds two parts of it. The diarizer works out **who spoke
when**, so an action item goes to the person who actually took it; the
challenge lists speaker diarization as a strong bonus. The minutes generator
([minutes/](minutes/README.md)) turns the transcript into Medpark's minutes
in Romanian, Russian and English, as PDF and DOCX, with every decision,
owner and deadline checked by code against the transcript. The branch also
holds the product's design system.

![The diarizer's test screen: five people introduce themselves, then hold a meeting in Romanian, Russian and English](diarization/demo/cli.gif)

The animation is our **test harness, not the product**. Secure MOM itself
is an internal web app (designs in [DESIGN.md](DESIGN.md) and the
[Figma file](https://www.figma.com/design/5gmJObntS61v2ehrmh01j9)); this
terminal screen is how we check the diarizer. In the recording, five people
with names from Moldova's 2025 birth records introduce themselves,
you type their names, and they hold a meeting. Maria switches between
Romanian and Russian. The screen marks a new voice with `+ NEW VOICE`, a
returning one with `↺ BACK`, and logs every turn with its start and end. The
voices are public recordings nobody in our training set spoke (see
[the demo notes](#the-demo-recording)), played through the live pipeline at
normal speed and sped up 2x in the GIF.

## Results at a glance

| What we measured | Result |
|---|---|
| Mixed Romanian / Russian / English meetings, 3 to 7 people, close microphone | **93.0% accurate**, 96.3% of turns given to the right person |
| 30-minute meetings with 11 to 14 people, close microphone | **93.6% accurate**, 95.9% of turns right |
| One microphone on the table, far from the speakers (AMI benchmark) | 66.5% accurate |
| Live test in a room with three people mixing languages | worked end to end |
| Speed on a 2017 Intel Core i5 laptop (2 cores, 8 GB) | 0.12x to 0.21x real time: an hour of audio takes 7 to 13 minutes |
| Delay between speech and its label, live | 1 second |
| Memory while running | 232 MB peak |
| Models on disk | 52 MB, bundled; nothing is downloaded at runtime |
| Network calls at runtime | none (a test fails the build if any code opens a socket) |
| Speakers per meeting | no limit set in advance; tested up to 14 in meetings and 100 in unit tests |
| Minutes: PDF per language, 2017 i5 | 4.3 s; RO, RU and EN compile in parallel |
| Tests | 74 passing in the diarizer, 87 in the minutes |

Accuracy here is 100 minus the diarization error rate (DER): the share of
time that was missed, falsely marked as speech, or given to the wrong
person, scored every 10 ms with no forgiveness collar and overlapping
speech included. That is the strict way to score. Turn accuracy is the
share of real turns that mostly went to the right person, which is how
often a line of the minutes gets the right name.

The honest weak spot is the third row. The Medpark sample recording sounds
like a far microphone (its speech is only 9 dB above the room), so until we
label real Medpark audio, expect numbers nearer 66% there than 93%.
Putting a microphone closer to the speakers moves a meeting into the first
two rows.

## Minutes

`mom report transcript.txt` writes six documents: a PDF (PDF/A-2b) and a DOCX
per language, in Medpark's colours, logo and type. A local model on
127.0.0.1 finds the facts and words them; code checks each one:

- the quote behind every fact is in the transcript lines it cites;
- a decision has a decision act in those lines, so a proposal nobody took up
  stays a note;
- owners are named or speaking in those lines, and deadlines are computed
  from the words said, never guessed;
- items that fail a check go to "Needs confirmation" for a person to settle
  before sending.

The wording follows 41 published hospital and public-body minutes in the
three languages (`minutes/research/corpus.md`). Sentences never say who
spoke; names appear only in the attendance list and on action owners, and
patients only as initials, age and bed. A PDF compiles in 4.3 s on the 2017
laptop, the three languages in parallel. The model is chosen by a bake-off
on Kaggle T4s over six scripted meetings with traps; its numbers go into
[minutes/README.md](minutes/README.md) when the run finishes.

## Try it

```bash
cd diarization
uv venv --python 3.11 && uv pip install -e '.[dev]'
source .venv/bin/activate && diarizer live
```

People introduce themselves one at a time, a few seconds each. Press Enter,
type a name for each voice it lists (or press Enter to keep "Speaker 1"),
then hold the meeting in any mix of languages. Press Enter again to finish;
the turns land in `sessions/<start time>/` as JSON, CSV and RTTM.

Other commands:

```bash
diarizer file meeting.m4a                       # a recording instead of the microphone
diarizer enroll "Maria" --language ro           # optional: remember a voice, with her agreement
diarizer voices                                 # who is enrolled, and when they agreed
diarizer voices forget "Maria"                  # delete her voiceprint
diarizer live --replay diarization/demo/meeting.wav   # the demo above, for testing
```

The full guide, including how the teammates' transcription step reads our
output, is in [diarization/README.md](diarization/README.md).

## What it needs to run offline

| Need | Detail |
|---|---|
| Computer | Tested on a 2017 MacBook Pro (Intel Core i5-7360U, 2 cores, 8 GB RAM, macOS 13). No GPU. The same packages exist for Linux and Windows, but we have not tested those. |
| Memory | about 250 MB free |
| Disk | 52 MB of models (in the repo) plus 323 MB of Python packages |
| Software | Python 3.10 or newer, ffmpeg (to decode m4a, mp3 and similar), and a microphone for live mode |
| Network | only once, to install the Python packages. Nothing after that. |

The challenge's reference server (one 16 GB GPU, or 32 GB RAM without a GPU)
is well above this. On it the diarizer can run at the same time as
transcription, so it adds almost nothing to the 15-minute target from the
end of a meeting to the email.

## How it works

Every half second, a small segmentation network (pyannote segmentation 3.0)
looks at the last 5 seconds of audio and marks who is talking in each 17 ms
frame, up to three people in the window and two at once. For each person in
the window, a voice model (NVIDIA's TitaNet-small) turns their clean speech
into a voiceprint of 192 numbers. A voiceprint describes how a voice
sounds, not what it says, so the same person speaking Romanian and then
Russian gets a similar one.

A tracker keeps every person heard so far: an average voiceprint plus a few
samples of their different tones. A new voiceprint close to someone known
goes to them. One far from everyone opens a new person. One in between goes
to the nearest person without changing what we remember about them, so one
bad guess does not spoil their profile. Two people who turn out to sound
the same are merged. Labels wait one second so the model has heard a little
past each moment. When the meeting ends, every observation is scored again
against the final voiceprints, which fixes early mistakes made before the
system knew everyone.

How far people sit from the microphone changes which settings work best, so
there are two profiles. For the first 10 seconds the diarizer measures how
far speech rises above the room's background noise. At 15 dB or more it
uses the close profile (our fine-tuned segmentation model); below that it
uses the far profile (the original model plus a voiceprint projection
trained on 38 AMI meetings to ignore room sound). Picking the wrong profile
costs 10 to 13 points, which is why the check runs by itself.

The neural parts are about 97% of the running time, and they already run
in C++ through ONNX Runtime. The rest is vectorised numpy.

## Compared with a paid cloud service

The best-known commercial diarization API is pyannoteAI. Its open model and
its paid model publish scores on AMI with a single distant microphone, the
same setting as our far-field test.

| | pyannoteAI Precision-2 (paid) | pyannote community-1 (open) | Secure MOM diarizer |
|---|---|---|---|
| AMI, single distant microphone, DER | **15.6%** | 19.9% | 33.5% |
| Where it runs | pyannoteAI's cloud, or self-hosted on an NVIDIA H100 | a GPU server | a 2017 laptop CPU |
| Speed | 14 s per hour of audio on an H100 | 31 s per hour on an H100 | 7 to 13 minutes per hour on a 2-core i5 |
| When labels appear | after the whole file is processed | after the whole file is processed | live, 1 second behind the speaker |
| Does audio leave the building | yes, for the cloud API | no | no |
| Price | €0.096 to €0.112 per hour of audio for the current Precision-3 | free | free |

Sources: the benchmark table in the
[pyannote.audio README](https://github.com/pyannote/pyannote-audio#benchmark)
(updated 2025-09, DER in %, full AMI test set) and
[pyannoteAI's model page](https://www.pyannote.ai/md/models) for prices.
Our number comes from 4 of the 16 AMI test meetings (ES2004a, IS1009a,
TS3003a, EN2002a), scored the same strict way, so treat the comparison as
close rather than exact.

The paid model is more than twice as accurate on far-microphone audio, and
we say so plainly. It also sends audio to a cloud, which the challenge
forbids, and it waits for the whole recording. Ours labels people while they
talk, on hardware a hospital already owns. For close-microphone meetings,
where we score 93%, we have no published paid-model number on the same
data to compare against.

## Training

We trained on Kaggle's free GPUs (two NVIDIA Tesla T4s per run) with public
data only. Hospital audio was never uploaded anywhere.

| Run | What it trained | Kaggle time | Of which training | Data downloaded |
|---|---|---|---|---|
| English | TitaNet-small voice model | 64 min | 34 min | 17.5 GB |
| Multilingual | TitaNet-small on Romanian, Russian and English | 121 min | 72 min | 47.2 GB |
| Gentle | TitaNet-small, frozen encoder, low learning rate | 46 min | 21 min | 35.1 GB |
| Segmentation | pyannote segmentation 3.0 | 87 min | 69 min | 41.9 GB |
| **Total** | | **5.3 hours** | **3.3 hours** | **142 GB** |

Every run did a smoke test and a preflight batch on real data before the
long part, and reported progress, time left and warnings every minute.
The reports are in [diarization/train/kaggle/runs/](diarization/train/kaggle/runs/).

The data, as the runs counted it:

| Dataset | Language | Hours used | Speaker labels | License | Citation |
|---|---|---|---|---|---|
| AMI Meeting Corpus | English (far and close microphones) | 40.1 h in voice training; 79.7 h (134 meetings) in segmentation | 152 | CC BY 4.0 | Carletta et al., *The AMI Meeting Corpus: A Pre-announcement*, MLMI 2005 |
| Common Voice 22 | Russian | 46.3 h | 2,997 | CC0 | Ardila et al., *Common Voice: A Massively-Multilingual Speech Corpus*, LREC 2020 |
| Common Voice 22 | Romanian | 24.6 h | 397 | CC0 | as above |
| VoxPopuli | Romanian | 19.6 h | 61 | CC0 | Wang et al., *VoxPopuli*, ACL 2021 |
| VoxConverse dev + test | English and others (broadcast) | 13.1 h + 20.4 h | 916 + 1,368 (per recording) | CC BY 4.0 | Chung et al., *Spot the Conversation*, Interspeech 2020 |
| AliMeeting | Mandarin (far-field meetings) | 2.0 h | 25 | CC BY-SA 4.0 | Yu et al., *M2MeT*, ICASSP 2022 |
| Simsamu | French (simulated medical calls) | small | | CC BY 4.0 | Simsamu, Hugging Face |
| OpenSLR 28 room impulses and noises | none (augmentation) | | | Apache 2.0 | Ko et al., *A study on data augmentation of reverberant speech*, ICASSP 2017 |

In total the multilingual run saw about 166 hours of speech and about 5,900
speaker labels. For the segmentation run we also built 300 synthetic
Romanian and Russian meetings from Common Voice voices, each voice passed
through its own room echo with background noise, so the model heard turn
changes in the languages Medpark speaks.

One tenth of Common Voice speakers (chosen by a hash of their ID) and every
speaker who recorded both Romanian and Russian were held out of all
training. The test meetings use only those voices.

What training taught us, in numbers:

| Change | Effect |
|---|---|
| Fine-tuning the TitaNet voice model (three runs) | never helped: voice separation d′ fell from 4.41 to 3.67, 3.90 and 4.28 |
| Fine-tuning the segmentation model | mixed-language accuracy 90.1% → 93.0%, turn accuracy 94.6% → 96.3%; but far-field AMI −3.3 points, so it ships only in the close profile |
| Choosing settings per microphone distance (no training at all) | mixed-language accuracy about 80% → 90% |
| Telling the diarizer how many people are present | worse: 93.6% → 89.2% on the large meetings, because it merges real people to hit the number |

The biggest gain came from measurement and configuration, not from GPU
hours. We kept the original voice model.

## How we tested

| Test set | Meetings | Audio | Turns | People per meeting | Answer key in repo |
|---|---|---|---|---|---|
| Mixed RO / RU / EN (6 to tune, 18 to score) | 24 | 88 min | 1,498 across both sets | 3 to 7 | [eval/references](diarization/eval/references/) |
| Large meetings | 4 | 120 min | (included above) | 11 to 14 | same folder |
| AMI far-field (8 dev meetings to tune, 4 test meetings to score) | 22 in the repo | 11.2 h scored | | 3 to 5 | [data/ami](data/ami/) (audio and labels) |
| Medpark sample recording | 1 | 11 min 43 s | not labelled yet | 4 heard | [data/Medpark_audio.m4a](data/Medpark_audio.m4a) |

The mixed meetings are built by `diarization/eval/make_mix.py` from the
held-out Common Voice voices plus LibriSpeech test-clean (English, CC BY
4.0, Panayotov et al., ICASSP 2015). Thresholds were tuned on the tuning
meetings only. The answer keys (who really spoke when) and the list of
voices in each meeting are committed, so the scores can be rebuilt with:

```bash
cd diarization
python -m eval.make_mix --meetings 24                      # downloads the public voices once
python -m eval.run_eval score --data ../data/mix/meetings --kind mix --embedder titanet-small
python -m eval.run_eval score --meetings ES2004a IS1009a TS3003a EN2002a   # AMI
```

## Security

We ran a focused review using the Cloudflare security-audit skill's attack
classes. Each control below is in the code and covered by a test.

| Attack class | What could go wrong | What we built | Where |
|---|---|---|---|
| Network and data exfiltration | any code path quietly sending audio out | no network code on the runtime path; the only networked command is `diarizer models fetch`, used once at setup | test `test_offline.py` blocks sockets and runs file mode end to end |
| Resource handling (SSRF, local file read) | a "recording" that is really a playlist or concat list makes ffmpeg open URLs or other files | files must start with a known audio signature (WAV, FLAC, MP3, MP4/M4A, OGG, WebM, CAF, AMR, WMA), and ffmpeg runs with `-protocol_whitelist file` | `diarizer/audio.py`, test `test_playlists_and_non_audio_files_are_refused`; 2,731 real audio files pass the check |
| Command injection | a file name or setting reaching a shell | ffmpeg is started with an argument list, never through a shell | `diarizer/audio.py` |
| Terminal injection | transcript text carrying escape codes that take over the terminal | control characters are stripped before printing | `_printable` in `diarizer/cli.py` |
| Path traversal | a person's name used to write outside the voices folder | names become file names only after reduction to letters, digits, `_` and `-` | `_slug` in `diarizer/voices.py` |
| Unsafe deserialization | a crafted voiceprint file running code when loaded | numpy loads with pickles disabled; no `pickle`, `eval` or `exec` anywhere in the diarizer | `diarizer/voices.py` |
| Archive extraction | a malicious archive writing outside its folder | tar files are opened with Python's `filter="data"` | `eval/make_mix.py` |
| Supply chain | a swapped model file | every downloadable model is pinned by SHA-256 and checked before use; the four models we need ship in the repo | `diarizer/models.py`, `models/NOTICE.md` |
| Secrets | tokens or keys in the repo | none; the Kaggle token was never committed, and a secrets scan of tracked files is clean | |
| Data isolation | another account on the same machine reading who spoke when, or voiceprints | session folders are created owner-only (0700) and their files 0600; the same for voiceprints | test `test_voiceprints_and_sessions_are_private` |
| Data lifecycle | voiceprints kept without consent or forever | enrollment asks for the person's agreement and stores when they gave it; `diarizer voices forget NAME` deletes every file of theirs | tests in `test_enroll.py` |
| Resource exhaustion | a very long file filling memory | a file is decoded whole: one hour is 230 MB. We accept this for a single-user local tool and note it under limitations. | |

Authentication does not apply to this part: it is a local command-line tool
that runs under the user's own account. Sign-in for the web app is an open
decision in [PRODUCT.md](PRODUCT.md).

## EU alignment scorecard

The GigaHack scorecard has 21 criteria, scored 0 to 4 by the team with a
mentor. Below is the evidence for each, from the diarization slice's point
of view, and the score we would propose. The final scores are agreed with
the mentor.

Two gaps turned up while filling this in, and we fixed them in code before
committing: enrolling a voice now records the person's consent (GDPR Art. 9
treats voiceprints as biometric data), and `diarizer voices forget` deletes
a person's voiceprints (Art. 17, the right to erasure).

| ID | Criterion | Evidence | Proposed |
|---|---|---|---|
| A1 | Green Deal problem fit | The product serves hospital administration rather than a Green Deal goal; its environmental angle is its small footprint (A3). | 1 Aware |
| A2 | Eco-design and circularity | Software only. It runs on computers a hospital already has, down to a 2017 laptop, so no new hardware is bought for it. | 2 Considered |
| A3 | Footprint of the tech itself | 52 MB of models, CPU only, 232 MB of RAM. About 2 to 3 Wh per meeting hour on a 15 W laptop chip. We dropped the larger voice models (101 MB and 114 MB) after measuring that they did not beat the small one. Training took 3.3 GPU-hours on shared Kaggle T4s. | 4 Evidenced |
| A4 | Do no significant harm | At 1,000 hospitals it still needs no data centre or new devices. It keeps no audio, so storage does not grow with use. | 2 Considered |
| B1 | Digital Europe capacity fit | Trustworthy AI and cybersecurity applied to healthcare administration, running on premises. | 3 Integrated |
| B2 | Trustworthy AI and AI Act | AI is in two places: finding speech and telling voices apart. Labels are anonymous by default (Speaker 1, 2). Naming people from their voice is biometric identification, which the AI Act treats with care, so it is opt-in, consented, local, deletable, and any label can be corrected by a person. It infers no emotions. In the minutes, a local model drafts the text; code checks every fact against the transcript, unconfirmed items wait for a person, and each PDF and DOCX is marked as AI-generated in its footer and metadata (Art. 50). Assessment: `minutes/compliance/ai-act.md`, `altai.md`. | 3 Integrated |
| B3 | Cybersecurity by design | The threat model and controls in the Security section, each with a test or a code reference. The minutes add a LaTeX macro whitelist with 14 injection tests, a model client that accepts only loopback and ignores proxies, and a CycloneDX SBOM (`minutes/compliance/sbom.json`). | 4 Evidenced |
| B4 | Use of EU digital infrastructure | Next step is testing in a real hospital setting through the EU's healthcare testing facility (TEF-Health) or a European Digital Innovation Hub. Not contacted yet. | 1 Aware |
| C1 | Personal data mapping and minimisation | We touch: audio (in memory only, never saved by the diarizer), turn times with labels, names typed by the user, and voiceprints of people who enroll. No audio is kept, and labels stay anonymous unless someone names them. The minutes hold no quotes, name patients only by initials, age and bed, and keep the checked facts in an owner-only file on the server (`minutes/compliance/data-inventory.md`). | 3 Integrated |
| C2 | Lawful basis and consent | Minutes: the hospital's legitimate interest in documenting its meetings (Art. 6). Voiceprints: explicit consent (Art. 9(2)(a)), now asked for and recorded with a time. Health details said in meetings belong to the transcript, handled by the transcription slice. | 3 Integrated |
| C3 | Privacy by design and by default | Local processing only, owner-only files, no audio retention, anonymous by default, one-command erasure. All tested. | 4 Evidenced |
| C4 | Experimentation ethics | All development used public recordings whose speakers consented (Common Voice, LibriSpeech, AMI). The live test used informed volunteers. The only hospital audio is the organisers' anonymised sample, which never went to a cloud. A DPIA (Art. 35) is needed before a real deployment; a draft is in `minutes/compliance/dpia.md`. The minutes were developed on synthetic meetings only, and the model bake-off ran on Kaggle with no hospital data. | 3 Integrated |
| D1 | Sector policy fit | Digital health: hospital records produced locally, in line with the EU's rules for health data. It makes no clinical decisions, so it is outside the Medical Device Regulation; the reasoning under MDCG 2019-11 is in `minutes/compliance/intended-purpose.md`. | 3 Integrated |
| D2 | Stakeholders and value chain | Meeting chairs, attendees, hospital IT and the data protection officer. Medpark set the requirements through the challenge; we have not interviewed them directly yet. | 2 Considered |
| D3 | Sector validation route | Label 5 minutes of real Medpark audio, then pilot in one board meeting with close microphones and measure accuracy there. | 2 Considered |
| D4 | Sector evidence and data standards | Standard DER scoring and RTTM output, results on a public benchmark (AMI), held-out test voices, answer keys in the repo. | 3 Integrated |
| E1 | EU market definition | Moldova first (Medpark), then Romania: same language, an EU member, and many private hospital networks. No market sizing yet. | 1 Aware |
| E2 | Value proposition and competition | Otter.ai, Fireflies.ai and Microsoft Teams recap run in the cloud; pyannoteAI sells diarization as a cloud API. Ours runs inside the hospital and handles Romanian and Russian switching mid-sentence. | 2 Considered |
| E3 | Business model for EU scale | A licence per hospital server is the working idea; the rest is team-level work. | 1 Aware |
| E4 | Market-entry requirements and costs | No CE marking, as it is not a medical device. GDPR and a DPIA apply, and hospitals fall under NIS2, which an offline design makes easier to meet. Costs not estimated yet. | 2 Considered |
| E5 | EU funding and growth pathway | Around TRL 4 to 5 (validated on benchmarks and a live test, not yet in a hospital). EIC Transition or Digital Europe and EDIH services fit that stage, and Moldova is associated to both Horizon Europe and Digital Europe. | 2 Considered |

## The demo recording

The five speakers in the GIF are public recordings: four from the held-out
part of Common Voice 22 (Romanian and Russian, CC0) and one from
LibriSpeech test-clean (English, CC BY 4.0). None of them is in our training
data. Their names come from Moldova's Public Services Agency birth records
for 2025: David and Sofia were the most given names, Maria was fourth among
girls, Alexandru seventh and Ion twentieth among boys
([diez.md, from the agency's data](https://diez.md/2025/12/26/topul-celor-mai-populare-prenume-de-baieti-si-fete-pe-care-le-au-ales-parintii-din-moldova-in-2025/);
David and Sofia also led in 2018, [IPN](https://www.ipn.md/en/david-and-sofia-are-most-popular-names-in-moldova-7967_1046798.html)).
Voices were matched to names by the speakers' recorded gender.

`python -m demo.make_demo` rebuilds the recording and its answer key, and
`vhs demo/cli.tape` records the GIF. In the recording, all 17 real turns
went to the right person, including every time someone came back after
another person spoke. It also shows one mistake we are still working on:
after the long pause following the introductions, the first second of speech
became a separate 1.5-second "Speaker 6". We left it in.

## Known limitations

- Far-microphone accuracy is 66.5% on AMI, against 15.6% DER (84.4%
  accuracy) for the best paid model. Closer microphones help most.
- After a long silence, the first second of the next speaker is sometimes
  labelled before the voice is recognised, which leaves a short extra
  speaker. The final pass fixes most of these, but not all.
- Accuracy on real Medpark meetings is unmeasured until someone labels a
  few minutes of them.
- A recording is decoded into memory whole: fine up to several hours on 8
  GB, but not built for day-long files.
- At most two people are recognised talking at the same moment.

## Tech stack

| Part | What we used |
|---|---|
| Language | Python 3.11 |
| Neural inference | ONNX Runtime 1.23.2 and sherpa-onnx 1.13 (C++ under the hood) |
| Speech segmentation | pyannote segmentation 3.0 (MIT), plus our fine-tuned version |
| Voiceprints | NVIDIA NeMo TitaNet-small (Apache 2.0) |
| Far-microphone projection | LDA and WCCN, trained by us on 38 AMI meetings |
| Numerics | numpy 2.4, scipy 1.17 |
| Audio in | sounddevice 0.5 (microphone), ffmpeg (files) |
| Terminal screen | rich 15, one amber colour, eighth-block waveform after cava |
| Training | Kaggle, 2x Tesla T4, PyTorch 2.10, CUDA 12.8, NVIDIA NeMo 3.0, Lightning 2.4, pyannote.audio 4.0.7 |
| Scoring | our own DER scorer (10 ms frames, no collar, overlap scored, optimal speaker mapping) |
| Tests | pytest, 74 tests, 849 lines |
| Design | Figma: 41 screens for desktop, tablet and phone, a 10-section style guide, 12 text styles and 59 colour variables |
| Demo | VHS by Charm |

About 3,900 lines of Python in the diarizer, evaluation and training code,
built in 36 commits between the evening of 25 September and the afternoon
of 26 September 2026.

## The design system

[DESIGN.md](DESIGN.md) and the Figma file describe the web app: three
sections (Meetings, Action items, People), three steps for every meeting
(Record, Minutes, Sent), upload or record, pick the meeting type, and the
minutes send themselves after a 60-second window in which anyone can stop
them. It covers every loading, error and empty state, English with a
Romanian and Russian switch, and fully offline operation.

Speaker colours come from Sanzo Wada's *A Dictionary of Colour
Combinations* (1933), through Matt DesLauriers's
[open dataset](https://github.com/mattdesl/dictionary-of-colour-combinations)
(MIT): 50 colours, the first five distinct for every pair even for
colour-blind viewers, all readable on the page.

## What's here

| Path | What it is |
|---|---|
| `diarization/` | The diarizer: live and file modes, enrollment, the demo, evaluation and training code |
| `diarization/eval/references/` | Answer keys for all 28 scored test meetings |
| `diarization/train/kaggle/runs/` | Reports from the four Kaggle training runs |
| `DESIGN.md`, `PRODUCT.md` | The design system and who the product is for |
| `data/` | The Medpark sample meeting and the AMI benchmark audio used for scoring |
| `harvard_health_scraper.py`, `harvard_medical_dictionary.*` | Medical vocabulary for the transcription side |
| `docs/` | The original design spec for the diarizer |

## How it fits the rest of Secure MOM

```bash
diarizer file meeting.m4a --out sessions/x
python -m asr_llm.cli meeting.m4a --diarization sessions/x/<id>.json   # samoilov-asr-llm branch
```

The diarizer writes `turns: [{speaker, start, end}]` in seconds from the
start of the file. The transcription and minutes step reads exactly those
fields and gives each transcript line a speaker, so the minutes can say who
took each action item.
