# How real hospital minutes are written

Every rule the minutes generator follows, and every phrase its templates use,
comes from the 41 published documents listed at the end of this file: board,
council and commission minutes from hospitals and health bodies in the United
Kingdom, the United States, Romania, the Republic of Moldova and Russia. We did
not invent a convention where the documents show one.

## Method

1. Found the documents through public board-paper pages and web search, then
   downloaded each one. Board packs were cut down to their minutes section.
2. Extracted text locally with `pdftotext`; scanned files went through
   `tesseract` OCR in Romanian or Russian. We did not rely on web summaries:
   asked to summarise one of these PDFs, a web summariser invented examples
   ("Dr. Ivanov") that are not in the document.
3. Counted how many documents use each decision, noting, action and deadline
   formula (`mine_formulas.py`, output in `formula-counts.json`). A formula found
   in many documents is a convention; one found in a single document is a
   house style.
4. Read the decision, action and attendance passages of each document by hand
   and coded them: structure, formulas, how people are named, how actions and
   deadlines are written, votes, sign-off, and what is left out.

## What we found

### English (13 documents, about 90,000 words)

Mostly NHS trust boards (Sheffield Health, University Hospital Southampton,
Harrogate, Airedale, Humber, Medway, Moorfields), plus UK health and wellbeing
boards and a US hospital district.

**Structure, in order.** Header with date, time, location and chair; *Present*,
*In attendance* and *Apologies*, each person with role and initials ("Paul
Grundy, Chief Medical Officer (PG)", `en_uhs_pack_2025-11`); welcome, apologies
and declarations of interest; minutes of the previous meeting; matters arising
and the action log; then the numbered items; any other business; date of the
next meeting.

**The most common formula is noting, not deciding.** "NOTED" appears 682 times
in 12 of 13 documents; "APPROVED" in all 13; "RESOLVED" in 9. Most business at a
board is received and noted. Decisions are rarer and marked:

- "RESOLVED that the minutes of the meeting held on 30 July be confirmed as a
  correct record and signed by the Chair." (`en_stockton_hwb_2025-09`)
- "Resolved: The minutes of the meeting on the 30 July 2025 were approved as an
  accurate record" (`en_hdft_pack_2025-11`)
- "Noting the discussions …, and having reviewed the proposed Operating Plan
  2025-26 …, the Board approved the Operating Plan 2025-26 and its submission,
  subject to the following:" (`en_uhs_pack_2025-11`)

**Discussion is reported, never quoted.** "The Board was informed that …",
"Members noted the ongoing pressures …" (`en_stockton_hwb_2025-09`); "It was
noted that …", "It was acknowledged that …" (`en_uhs_pack_2025-11`). Past tense,
third person.

**Actions name a person and a verb, and usually no date.** "Andy Hyett agreed to
carry out a deep-dive into Diagnostics …"; "Steve Harris and Andy Hyett agreed to
respond to the questions …" (`en_uhs_pack_2025-11`); "Action: To consider a Board
Workshop on …" (`en_hdft_pack_2025-11`). Every document marks actions, 9 keep a
separate action log, and dates sit in that log, not in the sentence. A deadline
is written only when one was set.

### Romanian and Moldovan (18 documents, about 59,000 words)

Moldova: the Government's secretaries-general meeting, Cantemir and Sîngerei
district councils, the Emergency Medicine Institute, the Ministry of Health,
the CRDM and Anenii Noi medical councils. Romania: Cluj county emergency
hospital's administration council, Brăila county hospital, the "Elena Doamna"
Iași hospital ethics council, the College of Dentists' national council, and a
2025 model proces-verbal.

**Structure, in order.** Institution; "PROCESUL-VERBAL nr.73 al ședinței … din
26 decembrie 2025" (`md_gov_pv73_2025-12`); place; who attended ("Au
participat:"), with the chair marked ("Roman CAZAN – Secretar general adjunct al
Guvernului, președinte al ședinței", surname in capitals); quorum in numbers
("din 33 consilieri aleși, la ședință sunt prezenți – 28", `md_cantemir_pv04_2024-06`);
"ORDINEA DE ZI:"; each subject; decisions; signatures of chair and secretary.

**Decisions are impersonal and reflexive.** "Se aprobă" (6 documents, 47 uses),
"HOTĂRÂRE" (7 documents), "s-a decis" (30 uses):

- "Ca urmare a discuțiilor din cadrul ședinței, s-a decis: Se acceptă propunerea
  dnei Voicu …" and "Se aprobă ordinea de zi cu 15 de subiecte" (`md_gov_pv73_2025-12`)
- "Consiliul de Administrație … emite următoarele hotărâri: 1. Se aprobă, cu 5
  voturi pentru, 0 abțineri și 0 voturi împotrivă, …", "2. Se avizează …",
  "4. Se recomandă Comitetului Director …" (`ro_cluj_hotarari_2021-05`)

**Votes are recorded as numbers.** "Propunerea este supusă votului. S-a votat:
pro-28, contra-0, abţinut-0." (`md_cantemir_pv04_2024-06`), or inline as above.

**People.** "dl / dna [Name], [function]" in Moldova; "Dr. [Name] - medic șef
secția …" in Romanian hospitals (`ro_braila_consiliul_medical`).

**Deadlines are dates.** "dd.mm.yyyy" appears in 13 documents; "în termen de …"
in 3; "responsabil" in 7.

### Russian (10 documents, about 28,000 words)

Tula children's regional hospital public council, supervisory boards of two
Novosibirsk institutions, a regional medical council, and Russian Ministry of
Health councils and commissions.

**Structure, in order.** "ПРОТОКОЛ заседания … от 4 мая 2023 г. №2"; who took
part (chair, secretary, members, invited), each as surname and initials with a
role ("Харитонов Д.В. - главный врач …", `ru_tula_dkb_obshsovet_2023-05`); groups as
counts ("64 чел.", `ru_social33_medsovet_2013-10`); the agenda with each speaker
in brackets; each item; decisions; the vote; signatures.

**The textbook form is rare.** СЛУШАЛИ / ВЫСТУПИЛИ / ПОСТАНОВИЛИ appears in one
document only. Modern protocols write "По первому вопросу выступил Харитонов Д.В.
- главный врач …, который представил …" and "По вопросу повестки дня: заслушали …"
(`ru_nso_nabsovet_17_2023`).

**Decisions are numbered infinitives under a heading.** "По итогам заседания
Общественного совета приняты решения: 1. Рекомендовать администрации …:
1.1. считать работу … удовлетворительной; 1.2. организовать проведение … 01.06.2023"
(`ru_tula_dkb_obshsovet_2023-05`); "РЕШИЛИ: Одобрить внесение изменений …"
(`ru_nso_nabsovet_17_2023`).

**Votes and closing.** "Проголосовали: «за» - 4 чел., «против» - 0 чел.,
«воздержались» - 0 чел. Решение принято единогласно." Then "Председатель …
О.И. Крупий", "Секретарь … Т.В. Ступина".

### What all three leave out

- Word-for-word speech. Every document reports what was said; none quotes it.
- Small talk and procedural chatter, beyond the opening and closing of the meeting.
- Patients' names. When individual cases appear, they are counted or described
  (complaints by topic, `ru_tula_dkb_obshsovet_2023-05`), not named. A patient
  story at a board is presented by the person, with their consent (`en_uhs_pack_2025-11`).
- Deadlines nobody set. When no date was agreed, none is written.

## Formula counts

**English** (13 documents, 90,104 words)

| Category | Formula | In documents | Uses |
|---|---|---|---|
| decision | `APPROVED` | 13 | 97 |
| decision | `(the )?(board/committee) (APPROVED/approved)` | 11 | 43 |
| decision | `RESOLVED` | 9 | 84 |
| decision | `carried` | 6 | 13 |
| decision | `it was agreed` | 5 | 51 |
| decision | `(board/committee) (AGREED/agreed)` | 5 | 10 |
| decision | `resolved that` | 3 | 5 |
| decision | `ratified` | 3 | 8 |
| decision | `motion` | 2 | 6 |
| decision | `endorsed` | 1 | 1 |
| noting | `NOTED` | 12 | 682 |
| noting | `(the )?(board/committee) (NOTED/noted)` | 11 | 83 |
| noting | `discussed` | 10 | 86 |
| noting | `it was noted` | 9 | 63 |
| noting | `received (the/a) (report/update/paper)` | 3 | 4 |
| noting | `was informed` | 3 | 7 |
| noting | `Members noted` | 3 | 6 |
| action | `ACTION` | 13 | 177 |
| action | `to (provide/circulate/report/bring/review/confirm) ` | 10 | 70 |
| action | `action log` | 9 | 19 |
| action | `agreed to` | 7 | 24 |
| action | `Action:` | 2 | 7 |
| action | `would (provide/report/circulate/bring)` | 1 | 1 |
| deadline | `\d{1,2}(st/nd/rd/th)? (January/February/March/April/May/June/July/August/September/October/November/December) 20\d\d` | 12 | 156 |
| deadline | `next (meeting/month/board)` | 7 | 13 |
| deadline | `by (the )?(end of )?(January/February/March/April/May/June/July/August/September/October/November/December)` | 5 | 8 |
| deadline | `due date` | 1 | 1 |

**Romanian and Moldovan** (18 documents, 58,629 words)

| Category | Formula | In documents | Uses |
|---|---|---|---|
| decision | `HOT[ĂA]R[ÂÎ]RE` | 7 | 41 |
| decision | `se aprob[ăa]` | 6 | 47 |
| decision | `unanimitate` | 4 | 13 |
| decision | `se accept[ăa]` | 3 | 5 |
| decision | `s-a decis` | 2 | 30 |
| decision | `a aprobat` | 1 | 1 |
| decision | `s-a hot[ăa]r[âî]t` | 1 | 1 |
| decision | `S-a votat` | 1 | 92 |
| decision | `se respinge` | 1 | 1 |
| noting | `a men[țţt]ionat` | 3 | 46 |
| noting | `a propus` | 3 | 13 |
| noting | `se ia act` | 2 | 22 |
| noting | `ia act` | 2 | 22 |
| noting | `a informat` | 1 | 2 |
| noting | `a prezentat` | 1 | 2 |
| noting | `a comunicat` | 1 | 1 |
| noting | `se consider[ăa]` | 1 | 1 |
| noting | `se aduce la cuno[șs]tin[țţ][ăa]` | 1 | 16 |
| action | `responsabil` | 7 | 28 |
| action | `va asigura` | 2 | 14 |
| action | `sarcin[ăa]` | 2 | 86 |
| action | `se oblig[ăa]` | 1 | 3 |
| action | `se [îi]ncredin[țţ]eaz[ăa]` | 1 | 1 |
| action | `se [îi]ns[ăa]rcineaz[ăa]` | 1 | 1 |
| action | `vor asigura` | 1 | 1 |
| action | `va prezenta` | 1 | 1 |
| deadline | `\d{1,2}\.\d{1,2}\.20\d\d` | 13 | 229 |
| deadline | `termen` | 4 | 136 |
| deadline | `p[âî]n[ăa] la` | 4 | 16 |
| deadline | `[îi]n termen de` | 3 | 107 |
| deadline | `permanent` | 2 | 2 |
| deadline | `lunar` | 2 | 3 |

**Russian** (10 documents, 28,147 words)

| Category | Formula | In documents | Uses |
|---|---|---|---|
| decision | `единогласно` | 3 | 3 |
| decision | `утвердить` | 3 | 5 |
| decision | `решение принято` | 2 | 2 |
| decision | `принять` | 2 | 2 |
| decision | `РЕШИЛИ` | 1 | 1 |
| decision | `решили` | 1 | 1 |
| decision | `одобрить` | 1 | 1 |
| noting | `выступил[аи]?` | 3 | 9 |
| noting | `представил[аи]?` | 2 | 5 |
| noting | `доложил[аи]?` | 1 | 3 |
| noting | `рассмотрен[ыо]?` | 1 | 1 |
| action | `рекомендовать` | 2 | 4 |
| action | `провести` | 2 | 2 |
| action | `ответственн(ый/ые/ая)` | 2 | 2 |
| action | `обеспечить` | 1 | 1 |
| action | `организовать` | 1 | 1 |
| deadline | `\d{1,2}\.\d{1,2}\.20\d\d` | 6 | 23 |
| deadline | `до \d{1,2}\.\d{1,2}\.20\d\d` | 3 | 3 |

## Sources (41 documents)

| ID | Language | Words | Source |
|---|---|---|---|
| `en_airedale_pack_2025-11` | English | 9,538 | [link](https://www.airedale-trust.nhs.uk/wp-content/uploads/2025/11/Combined-BoD-PUBLIC-agenda_papers-05.11.25-exc-14ib-FINAL.pdf) |
| `en_havering_2025-05` | English | 1,085 | [link](https://democracy.havering.gov.uk/documents/s79969/250507%20Minutes.pdf) |
| `en_hdft_pack_2025-11` | English | 9,348 | [link](https://www.hdft.nhs.uk/wp-content/uploads/2025/11/HDFT-Board-of-Directors-Meeting-PUBLIC-26th-November-2025-Final-Papers-Pack.pdf) |
| `en_humber_pack_2024-11` | English | 4,143 | [link](https://www.humber.nhs.uk/media/luqkif5k/public-board-papers-27-november-2024.pdf) |
| `en_medway_pack_2025-09` | English | 3,867 | [link](https://www.medway.nhs.uk/wp-content/uploads/2025/09/Trust-Board-in-Public-Meeting-Papers-September-2025.pdf) |
| `en_moorfields_pack_2025-10` | English | 6,630 | [link](https://moorfields.nhs.uk/mediaLocal/hdrb3i3d/251002-public-board-meeting-pack.pdf) |
| `en_sgmh_minutes_2024-06` | English | 1,036 | [link](https://www.sgmh.org/files/9a4ef1ad5/SGMH-Minutes-6-4-2024.pdf) |
| `en_sheffield_1` | English | 10,146 | [link](https://www.sheffieldpartnership.nhs.uk/sites/default/files/2026-01/04%20Public%20BoD%20Jan%202026%20unconfirmed%20minutes%20public%20BoD%20Nov%202025.pdf) |
| `en_sheffield_2` | English | 10,960 | [link](https://www.sheffieldpartnership.nhs.uk/sites/default/files/2026-03/04%20Public%20BoD%20March%202026%20unconfirmed%20minutes%20public%20BoD%20Jan%202026.pdf) |
| `en_sheffield_3` | English | 11,432 | [link](https://www.sheffieldpartnership.nhs.uk/sites/default/files/2026-05/04%20Public%20BoD%20May%202026%20unconfirmed%20minutes%20public%20BoD%20March%202026.pdf) |
| `en_sheffield_4` | English | 11,193 | [link](https://www.sheffieldpartnership.nhs.uk/sites/default/files/2026-07/04%20Public%20BoD%20July%202026%20Unconfirmed%20public%20BoD%20minutes%20May%202026%20F.pdf) |
| `en_stockton_hwb_2025-09` | English | 611 | [link](https://moderngov.stockton.gov.uk/documents/s21184/Health%20Wellbeing%20Board%20-%20Minutes%2024th%20Sep%2025.pdf) |
| `en_uhs_pack_2025-11` | English | 10,115 | [link](https://www.uhs.nhs.uk/Media/UHS-website-2019/Docs/About-the-Trust/Trust-governance-and-corporate-docs/2025-Trust-documents/Papers-Trust-Board-11-November-2025.pdf) |
| `md_anenii_noi_consiliul_medical.html` | Romanian (Moldova) | 478 | [link](https://anenii-noi.md/sedinta-consiliului-medical/) |
| `md_cantemir_pv04_2024-06` | Romanian (Moldova) | 21,562 | [link](https://www.cantemir.md/wp-content/uploads/2024/07/Proces-verbal-nr.04-din-13.06.2024.signed.signed.pdf) |
| `md_crdm_consiliul_medical.html` | Romanian (Moldova) | 977 | [link](https://www.crdm.md/pages/consiliul_medical.html) |
| `md_gov_pv73_2025-12` | Romanian (Moldova) | 1,348 | [link](https://gov.md/sites/default/files/media/documents/sedinte-de-guvern/2025-12/12.26.semnat.pdf) |
| `md_imu_po_consiliu_medical` | Romanian (Moldova) | 1,899 | [link](https://www.urgenta.md/PO%20nr.01.135%20Consiliul%20Consultativ%20Medical.pdf) |
| `md_ms_ordin_ca_imsp_2024` | Romanian (Moldova) | 2,135 | [link](https://ms.gov.md/wp-content/uploads/2024/02/Ordin-CA-IMSP-raionale.pdf) |
| `md_singerei_pv_2025-10` | Romanian (Moldova) | 21,433 | [link](https://singerei.md/wp-content/uploads/2025/11/proces-verbal-octombrie.signed.signed_redacted.pdf) |
| `ro_braila_consiliul_medical` | Romanian (RO) | 1,134 | [link](http://www.spitalbraila.ro/assets/docs/comisii/consiliul-medical.pdf) |
| `ro_cluj_hotarari_2021-04` | Romanian (RO) | 662 | [link](https://scjucluj.ro/pdf/intpublic/Hotarari%20CA%2008.04.2021.pdf) |
| `ro_cluj_hotarari_2021-05` | Romanian (RO) | 370 | [link](https://scjucluj.ro/pdf/intpublic/Hotarari%20CA%2017.05.2021.pdf) |
| `ro_cluj_hotarari_2021-06` | Romanian (RO) | 345 | [link](https://scjucluj.ro/pdf/intpublic/Hotarari%20CA%20%2010.06.2021.pdf) |
| `ro_cluj_hotarari_2021-07` | Romanian (RO) | 199 | [link](https://scjucluj.ro/pdf/intpublic/Hotarari%20CA%20%2001.07.2021.pdf) |
| `ro_cluj_reguli_ca` | Romanian (RO) | 858 | [link](https://scjucluj.ro/pdf/2020/mai/Reguli_de_func%C8%9Bionare_a_Consiliului_de_Administra%C8%9Bie.pdf) |
| `ro_cmsr_pv_cn_2023-12` | Romanian (RO) | 3,356 | [link](https://cmsr.ro/wp-content/uploads/2026/04/2023-12_Proces_verbal_de_sedinta_CN_CMSR_18.12.2023_updated_nosign.pdf) |
| `ro_elenadoamna_etic_1` | Romanian (RO) | 362 | [link](http://www.spitalelenadoamna.ro/documente/cosiliu_etic/2022/Proces_verbal_privin_rezultatele_votului_pentru_completarea_componentei_CE.pdf) |
| `ro_elenadoamna_etic_2` | Romanian (RO) | 467 | [link](http://www.spitalelenadoamna.ro/documente/cosiliu_etic/2024/Proces_verbal_alegeri_CE_04062024.pdf) |
| `ro_elenadoamna_etic_3` | Romanian (RO) | 647 | [link](http://www.spitalelenadoamna.ro/documente/cosiliu_etic/2024/Proces_verbal_alegeri_CE_05062024.pdf) |
| `ro_model_pv_ca_2025` | Romanian (RO) | 397 | [link](https://isj-db.ro/public/public/upload/manager/files/MANAGEMENT%20INSTITUTIONAL/2025/Model_Proces-verbal_Consiliul%20de%20administratie.pdf) |
| `ru_bpni_nabsovet_2022-10` | Russian | 1,128 | [link](https://bpni.nso.ru/sites/bpni.nso.ru/wodby_files/files/document/2025/03/documents/protokol_28.10.22_compressed.pdf) |
| `ru_minzdrav_konkurs_komissia` | Russian | 14,419 | [link](https://static-0.minzdrav.gov.ru/system/attachments/attaches/000/018/561/original/Protokol_zasedaniya_TCentralynoj_konkursnoj_komissii.doc) |
| `ru_minzdrav_lek_2024-08` | Russian | 4,478 | [link](https://minzdrav.gov.ru/ministry/61/10/stranitsa-858/stranitsa-7803) |
| `ru_minzdrav_mezhved_2023-07` | Russian | 342 | [link](https://minzdrav.gov.ru/ministry/stranitsa-7633) |
| `ru_minzdrav_patients_3_2024-08` | Russian | 335 | [link](https://minzdrav.gov.ru/open/supervision/patients/protokoly-zasedaniy/protokol-ot-29-avgusta-2024-g-3) |
| `ru_minzdrav_selektor` | Russian | 4,395 | [link](https://minzdrav.gov.ru/ministry/61/10/stranitsa-858/protokol-videoselektornogo-soveschaniya-pod-predsedatelstvom-zamestitelya-ministra-zdravoohraneniya-rossiyskoy-federatsii-n-a-horovoy) |
| `ru_nso_nabsovet_17_2023` | Russian | 340 | [link](https://xn--80adjnichn6a0a3g.xn--p1acf/wp-content/uploads/2023/06/%D0%9F%D1%80%D0%BE%D1%82%D0%BE%D0%BA%D0%BE%D0%BB-%D0%BD%D0%B0%D0%B1%D0%BB%D1%8E%D0%B4%D0%B0%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D0%BE%D0%B3%D0%BE-%D1%81%D0%BE%D0%B2%D0%B5%D1%82%D0%B0-%E2%84%9617.pdf) |
| `ru_social33_medsovet_2013-10` | Russian | 503 | [link](https://social33.ru/images/files/ps_111013.pdf) |
| `ru_tula_dkb_obshsovet_2023-03` | Russian | 832 | [link](https://med-bd-tdokb-r71.gosweb.gosuslugi.ru/netcat_files/7/160/Protokol_zasedaniya_obschestven._soveta_ot_22.03.23.pdf) |
| `ru_tula_dkb_obshsovet_2023-05` | Russian | 1,375 | [link](https://med-bd-tdokb-r71.gosweb.gosuslugi.ru/netcat_files/7/160/Protokol_zased._Obschestven._soveta_ot_04.05.23.pdf) |
