# Data

| File | What it is | Source | Licence |
|---|---|---|---|
| `medical_ro_ru_en.json` | 86 aligned Romanian / Russian / English medical and hospital terms, plus 2,034 English-only terms. The writing step uses the aligned rows only. | Copied unchanged from `asr-llm/data/medical_ro_ru_en.json` on the team's `samoilov-asr-llm` branch, built by the team's speech-recognition slice (see `asr-llm/data/SOURCES.md` there). Its layers: ICD-10 diagnosis titles from the Hugging Face dataset `birgermoell/icd10-clinical-notes`; hospital workflow terms curated by the team; English terms from `harvard_medical_dictionary.json` in this repository. | ICD-10 titles: as stated on the dataset card of `birgermoell/icd10-clinical-notes` (not re-checked here). Team-curated rows: the team's own work. Confirm the dataset card before any use outside the challenge. |

Nothing here is fetched at run time; the file is read from disk.
