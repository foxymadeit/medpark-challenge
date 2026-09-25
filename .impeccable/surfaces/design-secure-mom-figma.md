---
version: 1
slug: "design-secure-mom-figma"
primary_target: "design/secure-mom-figma"
related_targets: []
---

# Surface brief: Secure MOM product, alternative design (Figma)

Scope: every product screen as an alternative design, placed in the Figma file below the existing screens (file FVFMsFps4MIohho5Yy5QR3), plus a style guide section. Desktop 1440, tablet 1024, phone 390. Mode: Operate.
Audience and job: anyone attending a Medpark meeting starts it, records or uploads, checks the minutes and lets them send; everyone reads the minutes and their own action items.
Constraints: fully offline; UI in English with a RO/RU switch; minutes auto-send with an undo window; WCAG 2.2 AA; large touch targets.
Memorable moment: the "You are here" route marker moving stage by stage through a meeting.
Unresolved: authentication method.

Raises borrowed from declined challengers:
- Counts (timer, speakers found, turns) change as one crossfade, never a count-up.
- Every state reads without colour: department letter tiles, speaker badges with numbers, status words.
- Minutes read at one text size on a 62 to 70 character measure.
- The running recording has one labelled control and a live level meter.
- Processing is one route with stops, not a spinner.
- The undo window visibly empties at a steady rate.

## Direction contract
THESIS: Secure MOM is the hospital's own signage for meetings: one route from Record to Sent that always shows where you are. It refuses the SaaS dashboard of sidebar, KPI tiles and soft grey cards.
OWN-WORLD: Mineral corridor ground, white sign panels edged by a 2 px ink rule, department colour held to small tiles (Medical green, Executive blue, Administrative plum), one signal-yellow "You are here" marker, Overpass Bold for sign heads, Golos Text for reading, Overpass Mono for times. Arrows are the only ornament.
STORY: Someone walks up, reads one sign, starts the right meeting, watches voices get labelled, and lets the minutes leave on their own unless they stop them.
FIRST VIEWPORT: Home. A thin top bar with the name left and EN RO RU right; a full-width "Start a meeting" row of three department doors, each a third wide and 208 px tall: a white sign plate with a 2 px ink edge, a department-colour letter tile and an arrow (colour stays small, never a full field); below it "Your action items" as a floor directory. The doors are the primary action.
FORM: Hospital wayfinding signage, position 6 of 7, seed 4fc189d7.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
