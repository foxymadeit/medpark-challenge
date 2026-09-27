---
version: 2
slug: "design-secure-mom-figma"
primary_target: "design/secure-mom-figma"
related_targets: []
---

# Surface brief: Secure MOM product, alternative design (Figma)

Scope: every product screen as an alternative design in its own file, [Secure MOM v2](https://www.figma.com/design/5gmJObntS61v2ehrmh01j9) (the teammate's file FVFMsFps4MIohho5Yy5QR3 keeps only the diarizer test screens; its existing screens are untouched). The file has 16 desktop screens at 1440, 2 tablet screens (1194 landscape, 834 portrait), 4 phone screens at 390, one Romanian variant, two prototype flows, and a nine-section style guide. Mode: Operate.
Audience and job: anyone attending a Medpark meeting starts it, records or uploads, checks the minutes and lets them send; everyone reads the minutes and their own action items.
Constraints: fully offline; UI in English with a RO/RU switch; minutes auto-send with an undo window; WCAG 2.2 AA; large touch targets.
Memorable moment: the route marker sliding from Record to Sent (Smart Animate, 280 ms).
Unresolved: authentication method (sign-in screen assumes hospital accounts).

## Revision, 2026-09-25

The first direction (hospital wayfinding: yellow "you are here" marker, 2 px ink sign edges, Overpass, arrows as ornament) was dropped after review. The user asked for more serious screens, less text, HockeyStack and glasa.io as references, nothing cartoonish and nothing pointed.

Raises kept from the first round:
- Every state reads without colour: speaker names, status words, labelled danger.
- Minutes read at one text size on a 62 to 70 character measure.
- The running recording has one main control and a live level meter.
- Processing is the route with stops, not a spinner.
- The undo window visibly empties at a steady rate.

## Direction contract
THESIS: Secure MOM is a quiet instrument. It shows one reading at a time, is exact about numbers, and lets the minutes be the only loud thing on screen. It refuses the SaaS dashboard of KPI tiles, gradients and helper copy.
OWN-WORLD: Warm bone ground (#f7f6f3), white panels with a 1 px hairline and a barely visible three-layer shadow, one near-black ink, department colour held to dots and tints, eight validated speaker hues. Onest for signs, Golos Text for reading, Geist Mono for numbers. 10 px controls, 18 px cards, Phosphor Bold icons, no arrows as ornament.
STORY: Someone walks up, picks their board, records, sees voices get names, and lets the minutes leave on their own unless they stop them.
FIRST VIEWPORT: Meetings. A thin top bar (wordmark, five sections, network status, EN RO RU), then three department doors to start a meeting, then today's meetings with their state.
FINISH: reviewed from screenshots of every frame (desktop, tablet, phone, RO), both flows wired, DESIGN.md written at the repo root. No shipping rasters; the design lives in Figma.
