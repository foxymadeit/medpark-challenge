# Rules for extracting and writing minutes

Each rule below comes from the 41 real minutes in `corpus.md`. The evidence
column names the documents; `formula-counts.json` has the counts. The
extraction prompt, the verifier and the templates implement these rules and
nothing else.

## What counts as what

| # | Rule | Evidence |
|---|---|---|
| R1 | **Noting is the default; deciding is the exception.** Something presented, discussed or reported is *noted*. It becomes a *decision* only when the meeting approves, agrees, resolves, accepts or rejects it. Never turn "was presented" or "was discussed" into a decision. | English: "NOTED" in 12/13 documents (682 uses) against "APPROVED" in 13 (97) and "RESOLVED" in 9 (84). Romanian: "a menționat", "a prezentat", "se ia act" sit apart from "se aprobă". |
| R2 | **A decision needs a decision act in the transcript**: approve, agree, resolve, decide, accept, reject, or a vote. In Romanian: se aprobă, s-a decis, se acceptă, se avizează, se respinge. In Russian: одобрить, утвердить, решили, решение принято. A proposal nobody accepted stays a discussion point. | `en_uhs_pack_2025-11`, `md_gov_pv73_2025-12`, `ro_cluj_hotarari_2021-05`, `ru_nso_nabsovet_17_2023` |
| R3 | **A recommendation to another body is a decision with an addressee.** "Se recomandă Comitetului Director …", "Рекомендовать администрации …". The addressee is the owner. | `ro_cluj_hotarari_2021-05`, `ru_tula_dkb_obshsovet_2023-05` |
| R4 | **Conditions stay with the decision.** "approved … subject to the following:" keeps its list. | `en_uhs_pack_2025-11` |
| R5 | **An action has a named owner and a verb.** "{Owner} agreed to {verb} …". If the speaker says "I'll do it", the owner is that speaker (from diarization). An action with no identifiable owner goes to *Needs confirmation*, never to a guessed person. | `en_uhs_pack_2025-11` ("Andy Hyett agreed to …"), `en_hdft_pack_2025-11` |
| R6 | **A deadline is written only when one was set.** Real minutes leave it out otherwise; the English action logs carry dates only for agreed deadlines. Relative phrases ("până vineri", "до конца месяца", "by next meeting") become a date only if the meeting date is known, and the original phrase is kept. | `en_uhs_pack_2025-11`, `en_hdft_pack_2025-11`; Romanian dates as dd.mm.yyyy in 13 documents |
| R7 | **Votes are recorded as said.** Numbers if numbers were given ("pro-28, contra-0, abţinut-0"; «за» - 4 чел.); "unanimously / în unanimitate / единогласно" only if the meeting said so or the count shows it. No vote is invented for a decision taken by consensus. | `md_cantemir_pv04_2024-06`, `ro_cluj_hotarari_2021-05`, `ru_tula_dkb_obshsovet_2023-05` |
| R8 | **A later decision replaces an earlier one on the same matter.** Minutes record outcomes, not every turn of the debate; a reversal is recorded once, as the final decision. | Every decision block in the corpus states outcomes only |
| R9 | **Rituals appear only if they happened.** Apologies, declarations of interest, approval of previous minutes and the date of the next meeting are written only if the transcript contains them. Never "No declarations of interest were made" by default. | These sections vary between documents; they record what happened |

## How it is written

| # | Rule | Evidence |
|---|---|---|
| W1 | **Reported speech, past tense, third person. No quotes.** English: "The Board was informed that …". Romanian: "{Nume} a menționat că …". Russian: "выступил(а) …, который(ая) представил(а) …". | All 41 documents; none quotes speech |
| W2 | **Decisions in each language's own form.** English: "The Board approved …" or "RESOLVED that …". Romanian: impersonal reflexive "Se aprobă …", "Se recomandă …". Russian: numbered infinitives under "По итогам заседания приняты решения:" or "РЕШИЛИ:". | `patterns.{en,ro,ru}.json` |
| W3 | **People: name plus role, in the local format.** English: "Full Name, Role (INITIALS)". Moldova: "dl / dna Nume, funcția"; chair as "Prenume NUME – funcția, președinte al ședinței". Russian: "Фамилия И.О. - должность". | `en_uhs_pack_2025-11`, `md_gov_pv73_2025-12`, `ru_tula_dkb_obshsovet_2023-05` |
| W4 | **Section order per language** as in `patterns.*.json`: header, attendance, agenda, items, decisions, votes, sign-off. | See `corpus.md`, "Structure" for each language |
| W5 | **Patients are never named.** Initials, age and bed only ("Pacientul A.P., 54 ani, salonul 12"). The corpus names no patients; GDPR Art. 5(1)(c) asks for the minimum. | `ru_tula_dkb_obshsovet_2023-05` (cases by topic) |
| W6 | **Russian: prefer the modern form.** "По первому вопросу выступил …" and "РЕШИЛИ" over СЛУШАЛИ/ВЫСТУПИЛИ/ПОСТАНОВИЛИ, which appears in 1 of 10 documents. | `formula-counts.json` |
| W7 | **Moldovan orthography.** ș and ț with comma below, â and î as in official Moldovan documents. | `md_gov_pv73_2025-12` |
| W8 | **Plain, human prose.** No em dashes outside quoted names and titles, none of the banned vocabulary (humanizer and voice lists), varied sentence length, no filler, no summary of the summary. | Humanizer and voice skills; checked by the style lint |

## Precedence when rules conflict

Grounding (every fact has transcript lines) beats completeness (every decision
captured), which beats style. A true decision written plainly is better than a
beautifully phrased guess.
