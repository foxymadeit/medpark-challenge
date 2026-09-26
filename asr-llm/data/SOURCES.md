# Medical glossary sources

Runtime file: `data/medical_ro_ru_en.json` (local, no network).

| Layer | Source | Languages |
|---|---|---|
| `aligned` ICD-10 titles | [birgermoell/icd10-clinical-notes](https://huggingface.co/datasets/birgermoell/icd10-clinical-notes) — diagnosis names only, chapters I–XXI common codes | en, ro, ru |
| `aligned` hospital-ops | Curated meeting/hospital workflow (CT, internare, consiliu) | en, ro, ru |
| `english_extra` | `harvard_medical_dictionary.json` already in the repo | en |

Not bundled: SNOMED / UMLS (license), full CIM-10-AM PDFs.

The JSON is committed. Nothing fetches it at run time; the pipeline never opens a socket.

Whisper never sees the glossary. The LLM sees a retrieved subset of the aligned table (`retrieve.py`). `english_extra` is stored for later lookup, not stuffed into prompts.
