# ALTAI self-check

The EU's Assessment List for Trustworthy AI, answered for the minutes generator.

| Requirement | Our answer |
|---|---|
| Human agency and oversight | A person reviews unconfirmed facts; minutes wait 60 seconds before sending and anyone can stop them. The model proposes, code checks, people decide. |
| Technical robustness and safety | Every fact is checked against the transcript; the LaTeX the model writes is limited to a fixed set of commands; if the model's document fails the checks, a plain version is built from the verified facts. Measured on a test set (`eval/`). |
| Privacy and data governance | Local only; minimisation and retention in `data-inventory.md`; DPIA draft in `dpia.md`. |
| Transparency | AI-generated marking in the file metadata and on every page; each fact in `facts.json` links to its transcript lines. |
| Diversity, non-discrimination and fairness | Works in Romanian, Russian and English, including mixed sentences. Fluency is measured per language so no language gets second-class minutes. |
| Societal and environmental well-being | Runs on hardware the hospital already has; the smallest model that passes the gates is used; energy per report is measured. |
| Accountability | Model, version and checks are recorded with each set of minutes; the verification report counts confirmed, dropped and unconfirmed facts. |
