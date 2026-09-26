---
name: Secure MOM
description: Offline meeting minutes for Medpark. Calm, exact, quiet.
colors:
  ground: "#f7f6f3"
  panel: "#ffffff"
  hairline: "#eae6df"
  ink: "#101010"
  ink-secondary: "#5b544b"
  ink-tertiary: "#6f685f"
  danger: "#b3261e"
  danger-tint: "#fbeae8"
  speaker-1: "#b73f74"
  speaker-2: "#c27544"
  speaker-3: "#0093a5"
  speaker-4: "#6450a1"
  speaker-5: "#1a7444"
  speaker-6: "#d46d7a"
  speaker-7: "#006eb8"
  speaker-8: "#489b6e"
typography:
  display:
    fontFamily: "Onest, system-ui, sans-serif"
    fontSize: "40px"
    fontWeight: 500
    lineHeight: "46px"
    letterSpacing: "-0.025em"
  h1:
    fontFamily: "Onest, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: "34px"
    letterSpacing: "-0.02em"
  h2:
    fontFamily: "Onest, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: "26px"
    letterSpacing: "-0.01em"
  h3:
    fontFamily: "Onest, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: "22px"
    letterSpacing: "-0.005em"
  plate:
    fontFamily: "Onest, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: "16px"
    letterSpacing: "0.02em"
  body-lg:
    fontFamily: "Golos Text, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: "26px"
  body-md:
    fontFamily: "Golos Text, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: "22px"
  body-sm:
    fontFamily: "Golos Text, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "18px"
  button:
    fontFamily: "Golos Text, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: "20px"
  strong:
    fontFamily: "Golos Text, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: "22px"
  data-md:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: "20px"
  data-sm:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "18px"
rounded:
  control: "10px"
  card: "18px"
spacing:
  "4": "4px"
  "8": "8px"
  "12": "12px"
  "16": "16px"
  "24": "24px"
  "32": "32px"
  "48": "48px"
  "64": "64px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.panel}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 20px"
    height: "44px"
  button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 20px"
    height: "44px"
  button-danger:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.danger}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 20px"
    height: "44px"
  button-quiet:
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "44px"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.control}"
    height: "48px"
  card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.card}"
    padding: "24px"
---

# Design System: Secure MOM

The source of truth is the Figma file
[Secure MOM v2](https://www.figma.com/design/5gmJObntS61v2ehrmh01j9). Its
**Style guide** page covers everything below with live components, plus the
EN/RO/RU glossary and writing rules. The token names in this file match the
variables in the "Secure MOM v2" collection. In CSS they become
`--sm-<group>-<name>`, for example `--sm-ink-primary` and `--sm-signal-danger`.

## Overview

**Creative North Star: "The quiet instrument"**

Secure MOM is used by doctors and managers who have a few minutes between
meetings, often on a tablet lying flat on a table. The interface behaves like
a good clinical instrument: it shows one reading at a time, it is exact about
numbers, and it stays out of the way until something needs a decision. The
minutes are the only thing on screen that should feel loud.

The page is warm bone, cards are white with a 1 px hairline and a shadow you
notice only when it is missing. There is one ink. Red turns up only when
something is recording, failed, or can still be stopped. People get one colour
each, taken from Sanzo Wada's dictionary, always beside their name. Meeting
types are words, never colours. The references were HockeyStack and glasa.io for
restraint and density. We ruled out anything cartoonish, pointed or chatty.

**Key characteristics**

- One job per screen; everything else is one tap away.
- Built for someone who has never seen it: three sections, three steps, and one
  line of guidance where a first-time user has to choose.
- Very little text. Titles name the thing, and there are no helper paragraphs.
- Numbers (times, durations, dates, counts) are always set in Geist Mono.
- Minutes auto-send on a 60-second countdown that anyone in the room can stop.
  Longer would eat into the 15-minute target from the end of the meeting to
  the email.
- Soft corners everywhere, with no arrows or pointed shapes used as decoration.
- Fully offline. Everything runs on the hospital's own computer, so the copy
  never mentions the internet, the cloud, syncing or Wi-Fi.

## Colors

Warm neutrals and one near-black ink. Red for danger, and one Wada colour per person.

- **Surfaces.** `ground` is the page, `panel` is every card and sheet, and
  `hairline` is every divider and card edge at 1 px.
- **Ink.** Use three steps and no more. `ink` is for anything you read to act.
  `ink-secondary` is for meta lines. `ink-tertiary` is only for labels you can
  safely ignore; it still passes 4.5:1 on both surfaces.
- **Danger.** It is used for "Stop sending", destructive actions and errors,
  always together with a word.
- **No decorative colour.** Meeting types and statuses are words. There are no
  department colours and no icons in tinted squares.
- **Speakers.** Each voice gets the next slot, in order, as it appears. The 50
  colours come from Sanzo Wada's *A Dictionary of Colour Combinations* (1933),
  via mattdesl's MIT dataset, filtered to 3:1 on panel and ground, away from
  grey and from the danger red, and ordered by an exhaustive search checked
  with the dataviz palette validator (Machado 2009 colour-blind model):
  - **1 to 5** pass every check on every pair: normal ΔE ≥ 15, colour-blind
    ΔE ≥ 7.1. Wada's muted range has no larger fully distinct set.
  - **6 to 8** pass every check on neighbouring pairs (normal ΔE ≥ 16,
    colour-blind ΔE ≥ 9.2).
  - **9 to 50** are all different and all readable, but too close to tell
    apart by colour alone. Past 8 people the name does the work.
  A speaker colour is a 10 px dot before a name, or a timeline bar in a row
  labelled with the name. It is never text, a fill behind text, or a button.

| Slot | Hex | Wada name |
|---|---|---|
|  1 | `#b73f74` | Rosolanc Purple |
|  2 | `#c27544` | Cinnamon Rufous |
|  3 | `#0093a5` | Cerulian Blue |
|  4 | `#6450a1` | Blue Violet |
|  5 | `#1a7444` | Diamine Green |
|  6 | `#d46d7a` | Old Rose |
|  7 | `#006eb8` | Blue |
|  8 | `#489b6e` | Green |
|  9 | `#59256a` | Red Violet |
| 10 | `#653514` | Mars Brown Tobacco |
| 11 | `#004f46` | Dusky Green |
| 12 | `#4f4086` | Violet |
| 13 | `#7c4226` | Brown |
| 14 | `#007190` | Antwarp Blue |
| 15 | `#986f2d` | Orange Citrine |
| 16 | `#00978d` | Benzol Green |
| 17 | `#7d133a` | Pansy Purple |
| 18 | `#642d5e` | Violet Red |
| 19 | `#dd4027` | Red Orange |
| 20 | `#5a82b3` | Olympic Blue |
| 21 | `#da525d` | Eugenia Red B |
| 22 | `#064f6e` | Vandar Poel's Blue |
| 23 | `#8c4c62` | Veronia Purple |
| 24 | `#005b8d` | Helvetia Blue |
| 25 | `#704357` | Dark Slate Purple |
| 26 | `#009465` | Dull Viridian Green |
| 27 | `#e2625e` | Eugenia Red A |
| 28 | `#802626` | Pale Burnt Lake |
| 29 | `#648f7b` | Pistachio Green |
| 30 | `#d96629` | English Red |
| 31 | `#635a3a` | Deep Grayish Olive |
| 32 | `#80719e` | Dull Blue Violet |
| 33 | `#8b835b` | Dark Citrine |
| 34 | `#00908a` | Light Porcelain Green |
| 35 | `#713b4c` | Violet Carmine |
| 36 | `#66629c` | Dark Soft Violet |
| 37 | `#099197` | Green Blue |
| 38 | `#a36752` | Sudan Brown |
| 39 | `#437742` | Cossack Green |
| 40 | `#555832` | Lincoln Green |
| 41 | `#644b1e` | Sepia |
| 42 | `#819238` | Oil Green |
| 43 | `#84565b` | Purple Drab |
| 44 | `#1c4286` | Deep Lyons Blue |
| 45 | `#96874d` | Buffy Citrine |
| 46 | `#7a4456` | Taupe Brown |
| 47 | `#762c19` | Madder Brown |
| 48 | `#806e4b` | Light Brownish Olive |
| 49 | `#71502f` | Pale Raw Umber |
| 50 | `#40456a` | Violet Blue |

## Typography

- **Onest** is for signs: screen titles, meeting titles, card headings.
- **Golos Text** is for reading: summaries, lists, buttons.
- **Geist Mono** is for anything that counts.

Onest and Golos Text both cover Romanian diacritics and Cyrillic, so RO and RU
need no fallback. Keep Geist Mono to digits and times.

| Role | Use |
|---|---|
| `display` 40/46 | Sign-in line and hero figures only |
| `h1` 28/34 | Screen title, one per screen |
| `h2` 20/26 | Meeting title |
| `h3` 16/22 | Card and section titles |
| `plate` 12/16 | Group labels over lists ("Today") |
| `body-lg` 17/26 | Summaries people read in full, 62 to 70 characters a line |
| `body-md` 15/22 | Default reading text |
| `body-sm` 13/18 | Meta lines |
| `button` 15/20 | Buttons and tabs |
| `strong` 15/22 | Names and list titles |
| `data-md` / `data-sm` | Timers, dates, durations |

Everything is sentence case. Dates read "Mon 28 Sep" and times use 24 hours.

## Layout

The spacing base is 4 px (steps 4, 8, 12, 16, 24, 32, 48, 64).

| Width | Grid | Behaviour |
|---|---|---|
| 1280 and up | 12 columns, 24 gutter, 64 margin (1440 frame, 1312 content) | Top bar with three sections: Meetings, Action items, People. All meetings (history) opens from the Meetings screen; System opens from the account initials. Minutes has a people rail on the right. |
| 768 to 1279 | 8 columns, 20 gutter, 32 margin | Recording sits side by side in landscape (1194). Minutes stacks in portrait (834). |
| under 768 | 4 columns, 16 gutter, 20 margin (390 frame) | Bottom tab bar: Meetings, Action items, People. System lives in the account menu. |

Leave room for text to grow by 35% for RO and RU. The route labels
("Proces-verbal") are the first thing to break.

## Elevation & Depth

Depth is barely there. There are three shadows, all in ink and stacked from
tight to wide:

- **card**: `0 1px 2px / 4%`, `0 4px 12px / 4%`, `0 16px 32px / 3%`. For resting cards and panels.
- **lift**: `0 2px 4px / 5%`, `0 8px 20px / 6%`, `0 24px 48px / 5%`. For menus, dialogs and the arriving send countdown.
- **button**: a 1 px inner white highlight at 16%, plus `0 1px 2px / 12%` and `0 4px 8px / 8%`. Primary buttons only.

Nothing else casts a shadow. Lists inside cards are separated by hairlines, not by more cards.

## Shapes

Controls (buttons, inputs, checkboxes, the language switch) use 10 px corners.
Cards, sheets and dialogs use 18 px. Dots are full circles: a speaker's colour, or the red recording pulse. Nothing is square and nothing is pointed. Chevrons appear only inside
a select, and arrows are never used as decoration. Every card edge is a 1 px
hairline.

## Components

All live on the **Components** page. Every interactive component has Default,
Pressed, Disabled and Focus states.

- **Button**: Primary, Secondary, Danger, Quiet; 44 px tall, with an optional
  leading Phosphor Bold icon. Use one Primary per screen. Danger is only for
  "Stop sending" and delete.
- **Door**: the three meeting types on the start screen: a name and where the
  minutes go. No icon, no colour. The whole door is the target.
- **Speaker**: colour dot, name, talk time.
- **Status**: a word on a neutral chip. Only Recording and Failed are red.
- **Language switch**: EN, RO, RU, always top right. It switches the whole
  interface and the page `lang`.
- **Input**: 48 px, with the label above the field and never inside it.
- **Route**: three stops, Record, Minutes, Sent. Transcribing and finding
  speakers happen inside Minutes; the user never has to know those words.
- **Send countdown**: the undo window. "Stop sending" stays visible and is
  first in tab order.
- **Action item**: task, owner (speaker), deadline, and when it was said.
- **Needs confirmation**: takes the countdown's place when the checks could
  not confirm an item against the transcript. Each item gets its reason in
  one line and two buttons, "Take out" and "Keep". Sending waits until every
  item is settled.
- **Documents**: one row per language (Română, Русский, English) with PDF and
  DOCX, then how many items were checked against the transcript and the
  AI-drafted notice.
- **Top bar**: wordmark, sections, the "Hospital network only" status, language.
- **Loader**: three dots stepping every 0.35 s, for waits under 10 s.
- **Skeleton**: grey bars with a sheen crossing in 1.2 s, for loading lists.
- **Check**: rises from 90% to full size in 240 ms, once, for success.
- **Recording pulse**: a red dot with a fading ring every second. It always
  sits next to the word Recording and a timer.
- **Toast**: Success, Error, Service, Undo. Bottom centre, one at a time,
  4 s, and any action stays until it's used.

### States

| State | Rule | Screens |
|---|---|---|
| Loading | A skeleton after 300 ms, loader dots for waits under 10 s, and an ETA in clock time for anything longer | X01, E04, S06, M01 |
| Empty | Say what is missing and offer one way to fill it | X08 |
| Error | Say what happened and that nothing was lost, then offer one next step and a reference code for IT | X02, X03, X04, E06 |
| Service not answering | Recording carries on and is saved locally; processing resumes by itself | X05, X09 |
| Sending stopped | Replaces the countdown in place, with one button to send | X10 |
| Needs a person | Replaces the countdown in place; sending waits until each unconfirmed item is kept or taken out | M03 |

Voice enrollment (E01 to E09) is optional. Without it, voices appear as
Speaker 1, 2, 3 and can be named after the meeting. The reading passages
live in `diarization/diarizer/passages.py`.

The minutes row (M01 to M03) shows what happens after "Writing the minutes":
M01 opens that stage up (transcript read, decisions found, each item checked
with a live count, writing in three languages, making PDF and DOCX). M03 is
the stop for items the checks could not confirm. M02 is the finished screen
with the six documents. The minutes themselves carry no names in their
sentences; people appear only in the attendance list and as action owners.

### Motion

| Moment | Duration and curve |
|---|---|
| Button press | 120 ms, `cubic-bezier(0.23, 1, 0.32, 1)`, scale 0.97 |
| Hover (mouse only) | 150 ms ease, background tint only |
| Screen change | 280 ms, same ease-out; shared parts stay, new parts fade and rise 8 px |
| Route marker | 280 ms, `cubic-bezier(0.77, 0, 0.175, 1)` |
| Countdown arrives | 240 ms ease-out, rises 12 px with the lift shadow |
| Send countdown bar | 60 s linear |
| Auto-advance (processing to minutes, loading to content) | 200 ms dissolve |
| Loader dots | 0.35 s per step, looping |
| Skeleton sheen | 1.2 s across, then restarts |
| Success check | 240 ms ease-out, once |
| Toast in and out | 200 ms ease-out, from and to the bottom |
| Tabs, keyboard, menus | Instant |

With `prefers-reduced-motion`, every movement becomes a 150 ms fade. The
countdown bar still empties, because it carries meaning.

## Do's and Don'ts

**Do**

- Use buttons that say what happens: "Send now", "Stop sending", "Write the minutes".
- Put a name next to every speaker colour and a word next to every status.
- Keep a 2 px ink focus ring with a 2 px offset on every control.
- Make "Now speaking" and the countdown polite live regions, and read the timer only on request.

**Don't**

- Colour-code meeting types, put an icon in a tinted square, or use a speaker colour as text or a fill.
- Add helper paragraphs, empty-state illustrations or emoji.
- Use pill-shaped cards, pointed shapes, or arrows as ornament.
- Animate anything people do many times a day.
- Write "Submit", "Oops", or an exclamation mark in the interface.
