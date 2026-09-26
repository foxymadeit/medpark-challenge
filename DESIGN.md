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
notice only when it is missing. There is one ink. The only colour is red, and
it turns up only when something is recording, failed, or can still be stopped.
Meeting types and speakers are told apart by their names, never by colour. The references were HockeyStack and glasa.io for
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

Warm neutrals and one near-black ink. Red is the only colour.

- **Surfaces.** `ground` is the page, `panel` is every card and sheet, and
  `hairline` is every divider and card edge at 1 px.
- **Ink.** Use three steps and no more. `ink` is for anything you read to act.
  `ink-secondary` is for meta lines. `ink-tertiary` is only for labels you can
  safely ignore; it still passes 4.5:1 on both surfaces.
- **Danger.** It is used for "Stop sending", destructive actions and errors,
  always together with a word.
- **No decorative colour.** Meeting types, speakers and statuses are words.
  There are no department colours, speaker colours, coloured dots, or icons in
  tinted squares. Speaker timelines use ink bars, one row per named person.

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
Cards, sheets and dialogs use 18 px. The only dot is the red recording pulse. Nothing is square and nothing is pointed. Chevrons appear only inside
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
- **Speaker**: name and talk time.
- **Status**: a word on a neutral chip. Only Recording and Failed are red.
- **Language switch**: EN, RO, RU, always top right. It switches the whole
  interface and the page `lang`.
- **Input**: 48 px, with the label above the field and never inside it.
- **Route**: three stops, Record, Minutes, Sent. Transcribing and finding
  speakers happen inside Minutes; the user never has to know those words.
- **Send countdown**: the undo window. "Stop sending" stays visible and is
  first in tab order.
- **Action item**: task, owner (speaker), deadline, and when it was said.
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
| Loading | A skeleton after 300 ms, loader dots for waits under 10 s, and an ETA in clock time for anything longer | X01, E04, S06 |
| Empty | Say what is missing and offer one way to fill it | X08 |
| Error | Say what happened and that nothing was lost, then offer one next step and a reference code for IT | X02, X03, X04, E06 |
| Service not answering | Recording carries on and is saved locally; processing resumes by itself | X05, X09 |
| Sending stopped | Replaces the countdown in place, with one button to send | X10 |

Voice enrollment (E01 to E09) is optional. Without it, voices appear as
Speaker 1, 2, 3 and can be named after the meeting. The reading passages
live in `diarization/diarizer/passages.py`.

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
- Name every speaker and every status in words.
- Keep a 2 px ink focus ring with a 2 px offset on every control.
- Make "Now speaking" and the countdown polite live regions, and read the timer only on request.

**Don't**

- Colour-code meeting types or speakers, or put an icon in a tinted square.
- Add helper paragraphs, empty-state illustrations or emoji.
- Use pill-shaped cards, pointed shapes, or arrows as ornament.
- Animate anything people do many times a day.
- Write "Submit", "Oops", or an exclamation mark in the interface.
