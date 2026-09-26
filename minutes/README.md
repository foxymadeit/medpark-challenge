# minutes

Turns a meeting transcript into Medpark's minutes, in Romanian, Russian and
English, as PDF and DOCX, with every fact checked against the transcript. It
runs on the hospital's own computers with no network.

This folder starts with the research the generator is built on:

- `research/corpus.md`: how 41 real hospital and public-body minutes are written,
  in English, Romanian (Romania and Moldova) and Russian, with sources.
- `research/rules.md`: the rules for what counts as a decision, an action, an owner
  and a deadline, and how each language writes them, each backed by the corpus.
- `research/patterns.{en,ro,ru}.json`: the same, for the prompts and templates to read.
- `research/models.md`: which local models could do this, and how we choose.
- `compliance/`: intended purpose, AI Act assessment, personal-data inventory,
  a draft DPIA and an ALTAI self-check.
