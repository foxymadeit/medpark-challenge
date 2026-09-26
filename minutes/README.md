# minutes

Turns a meeting transcript into Medpark's minutes, in Romanian, Russian and
English, as PDF and DOCX. Every decision, action, owner and deadline in them
is checked by code against the transcript lines it came from. It runs on the
hospital's own computers with the network off.

```bash
mom report meeting.txt --type medical --date 2026-09-26 --start 14:10
```

It prints how many facts passed the checks, how many need a person and how
many were dropped, then the six file paths and the time each stage took.

The minutes read like the ones hospitals already publish. They cover the
agenda, what the board was told, what it decided and who does what by when.
Sentences never say who spoke: "The Board was informed that …", "S-a
propus …", "Совет проинформирован, что …". People appear in two places, the
attendance list and the owner of an action. When nobody says a name in the
recording, they are "Participant 1, 2, 3" from the diarizer.

Sample output: `examples/sample_{ro,ru,en}.pdf`.

## Setup

```bash
cd minutes
pip install -e '.[dev]'          # python-docx and rapidfuzz, nothing else at run time
```

Three things have to be on the machine before the network goes off:

1. **TeX Live** with XeLaTeX and these packages: `pdfx`, `fontspec`,
   `polyglossia`, `xltabular`, `colortbl`, `ragged2e`, `needspace`,
   `hyphen-romanian` and `hyphen-russian`. On macOS: MacTeX, then
   `sudo tlmgr install hyphen-romanian hyphen-russian`.
2. **Ollama** with the model pulled once: `ollama pull qwen3:8b`. The
   pipeline only talks to it on 127.0.0.1. llama.cpp's `llama-server` works
   too (`--url http://127.0.0.1:8080`).
3. **Fonts for DOCX** (optional): the PDF embeds Montserrat and PT Serif
   from `template/fonts/`. Word uses whatever is installed, so install those
   eight files on the machines that open the DOCX, or Word substitutes its
   own fonts.

## Use

```bash
mom report TRANSCRIPT [options]
```

| Option | What it does |
|---|---|
| `--session diarizer.json` | the diarizer's session file; speakers come from its turns |
| `--type medical\|executive\|administrative` | picks the body name (Consiliul Medical, Executive Board, ...) |
| `--date 2026-09-26` | meeting date; relative deadlines ("până vineri", "до пятницы") resolve from it |
| `--start 14:10` | clock time the recording started |
| `--number 14`, `--place`, `--chair`, `--secretary` | header fields, printed as given |
| `--lang ro,ru,en` | which documents to write (default all three) |
| `--out DIR` | where the files go (created 0700) |
| `--model qwen3:8b`, `--url` | the local model and its loopback address |
| `--think off\|low\|medium\|high` | reasoning effort for models that have it, extraction only |

`mom purge out/ --days 30` deletes minutes files older than the retention
period the hospital sets; run it daily from cron or a systemd timer.

The transcript can be plain text (with or without `[00:12:03]` stamps and
`Speaker 2:` labels), SRT, VTT, or JSON from whisper, whisper.cpp,
faster-whisper or our own ASR. Files over 20 MB are refused.

Each run writes, per language, a PDF (PDF/A-2b) and a DOCX, then two JSON files:

- `MoM_<date>_<type>.facts.json`: every fact with its transcript line IDs,
  the quote it was checked against, its status and any problem found. It
  stays on the server (mode 0600) and is never sent: the minutes themselves
  hold no quotes.
- `MoM_<date>_<type>.report.json`: counts, timings, token use, the model
  name and the digest of the model file that wrote it.

## How it works

```
transcript ──► 1 normalize   numbered lines: L0012 [Speaker 2] text
           ──► 2 extract     local model, JSON schema, temperature 0, 10-min windows with 1-min overlap
           ──► 3 verify      code only: each fact kept, sent to "needs confirmation", or dropped
           ──► 4 merge       duplicates across windows joined, IDs T1 N1 D1 A1
           ──► 5 anonymize   patients become initials, age and bed
           ──► 6 write ×3    the model writes the LaTeX body per language, using only our macros
           ──► 7 check body  whitelist, every fact present, owners and deadlines forced back, no new numbers or names
           ──► 8 render      XeLaTeX → PDF, python-docx → DOCX, all three languages in parallel
```

The model does two jobs: find the facts, and word them. Everything that can
be computed is computed by code instead.

**What the verifier checks** (`mom/verify.py`):

1. The quote the model gives is in the lines it cites (rapidfuzz, diacritics
   folded, score 92 or more). A fact with no matching quote is dropped.
2. A decision needs a decision act in its lines: an approval formula in one
   of the three languages, or a proposal followed by someone agreeing
   ("bine, facem", "ладно", "fine"). A proposal nobody took up stays a note.
3. An owner must be named in the cited lines, or be the speaker who said
   "I'll do it". Otherwise the item needs confirmation, and so does an action
   with no owner at all.
4. Deadlines are resolved by code from the words said ("până vineri", "через
   две недели", "by the end of the month"). A deadline nobody said is removed.
   One that cannot become a date ("early next week") is printed as said,
   never turned into an invented date.
5. A number or a name in a fact that is not in its lines sends the fact to
   confirmation.

Anything that fails 3 or 5 goes under "Needs confirmation" in the document
and on the confirmation screen, so a person decides before sending. The PDF
footer says how many items were checked ("11/11 items checked against the
transcript") and that the text was drafted locally by AI.

**What the body check does** (`mom/latexcheck.py`, `mom/write.py`): the model
can use nine macros (`\summary`, `\agendaitem`, `\topic`, `\presented`, `\noted`, `\decision`,
`\action`, `\needsconfirmation`, `\nextmeeting`) and the `agenda` environment,
each fact tagged with its ID, and nothing else: no `\input`, no `\write`, no
catcodes, no text outside a macro, no unknown IDs.
Every verified fact has to appear; owners and deadlines are overwritten with
the verified values; numbers and names not in the evidence fail the check.
One repair round, then a plain body built directly from the verified facts,
so a document always comes out.

**Prompts** (`prompts/`): the extraction prompt puts the hard rules first
(only these lines, cite IDs, a proposal is not a decision, unknown means
empty), then an ordered procedure, the corpus definitions, a list of known
wrong outputs and a worked trap. The writing prompt carries each language's
formulas from the corpus (`style_{ro,ru,en}.md`) and the plain-prose rules:
no em dashes, no filler, past tense, no names in sentences.

## Research behind it

`research/corpus.md` codes 41 published minutes: 13 English (NHS trust boards
and health boards), 18 Romanian (Moldovan hospital councils, district
councils, Romanian hospital boards) and 10 Russian (medical councils and
hospital protocols). Every source is downloaded and read locally; the URLs
are in the file. Some of what it found, and where it went:

| Finding | Used for |
|---|---|
| "NOTED" appears in 12 of 13 English documents, 682 times: most items are noted, not decided | extraction defaults to a note |
| No document quotes speech or names a patient | minutes hold no quotes; patients as initials |
| Moldovan votes read "S-a votat: pro-28, contra-0, abținut-0" | vote wording in Romanian |
| Modern Russian protocols write "По первому вопросу выступил" and "РЕШИЛИ"; СЛУШАЛИ appears in 1 of 10 | Russian style |
| English actions are "X agreed to …", usually with no date | no invented deadlines |

`research/rules.md` holds the extraction and writing rules with the quote
behind each one; `research/patterns.{en,ro,ru}.json` has the same for code.

## Model

Picked by a bake-off on Kaggle T4 GPUs (16 GB, the reference card), never on a
laptop, using only the synthetic meetings below. Candidates, gates and the
published evidence (hallucination rates, Romanian grounded-task scores) are in
`research/models.md`. The GPU tier tries dense 4 to 14B models (Gemma 3 and 4,
Qwen 3, Phi-4, Mistral Small, EuroLLM-22B); the 32 GB CPU tier tries
mixture-of-experts models with 3 to 4B active parameters (gpt-oss-20b,
Qwen3-30B-A3B, Gemma 4 26B).

Round 1 (six scripted meetings, 16.4 min, 15 decisions, 15 actions, 6 traps) put
`qwen3:8b` first: 100% of decisions found and all correct, 93% of actions, 0
traps, 7.2 GB of GPU memory. It is the default; round 2 re-scores the top eight
with the date fixes and a 60-minute meeting. The full table is in the
[root README](../README.md#2-output-quality-30).

## Measured

- **PDF**: 4.3 s per document on a 2017 Intel i5, three languages compiled in
  parallel. The logo is a vector PDF (no TikZ), and XeLaTeX runs twice, a
  third time only if the log asks.
- **Tests**: 87, including a full run with the network blocked at the socket
  level and 14 LaTeX injection attempts.
- **Evaluation set** (`eval/meetings.py`): six scripted meetings, two per
  type, mixing Romanian, Russian and English inside sentences. They hold 15
  decisions and 15 actions with known owners and deadlines, plus traps: six
  proposals nobody adopts, two decisions reversed later, "I'll do it" with the
  owner known only from the speaker label, relative deadlines and named
  patients. `eval/score.py` scores recall, precision, owner and deadline
  accuracy and trap errors.

## Security

- **No network:** the model client refuses any address that is not loopback,
  ignores `HTTP_PROXY` and similar settings, and refuses redirects, so a
  transcript cannot leave the machine even through a misconfigured proxy.
  The end-to-end test blocks sockets and passes.
- **LaTeX:** header values are escaped by code. The model's body goes through
  the macro whitelist. XeLaTeX runs with shell escape off, `openin_any` and
  `openout_any` set to paranoid, in a private temporary folder.
- **Files:** the output folder is 0700, every file in it 0600.
- **Patients:** names become initials before the writing step, and the body
  check fails on any name pair that is not in the evidence.
- **Supply chain:** `compliance/sbom.json` (CycloneDX 1.5) lists the Python
  packages, the fonts and logo with SHA-256 hashes, and the local tools;
  `python compliance/make_sbom.py` rebuilds it.

## EU compliance

| Topic | File |
|---|---|
| What it is for, and why it is not a medical device (MDCG 2019-11) | `compliance/intended-purpose.md` |
| AI Act: limited risk; Art. 50 marking in PDF metadata, footer and DOCX properties | `compliance/ai-act.md` |
| Personal data per step, retention, legal basis (GDPR Art. 6, 9(2)(h)) | `compliance/data-inventory.md` |
| Draft DPIA (GDPR Art. 35) | `compliance/dpia.md` |
| ALTAI self-check | `compliance/altai.md` |
| Moldova Law 195/2024 | covered in the data inventory |

## Evaluate

```bash
python -m eval.meetings                 # writes eval/data/*.txt and *.gold.json
python -m eval.bakeoff --models gemma3:4b,qwen3:8b --out results/   # needs Ollama on 127.0.0.1
kaggle kernels push -p eval/kaggle      # the full bake-off on a Kaggle T4
pytest
```
