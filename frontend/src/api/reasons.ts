import type { TFunction } from "i18next";

// What the minutes checks write when they cannot confirm an item
// (minutes/mom/verify.py), and the sentence a reader should see instead.
const KNOWN: [RegExp, string][] = [
  [/^action without an owner/i, "reason_noOwner"],
  [/^owner .* is not named or speaking/i, "reason_ownerNotHeard"],
  [/^deadline .* was not said/i, "reason_deadline"],
  [/^number .* is not in the evidence/i, "reason_number"],
  [/^quote not found/i, "reason_quote"],
  [/^name .* appears nowhere/i, "reason_name"],
  [/^no decision act/i, "reason_notAgreed"],
];

/** One localised sentence per check that failed; text the app does not
 * know yet is shown as the server wrote it rather than hidden. */
export function explainProblems(problems: string[], t: TFunction): string {
  const out: string[] = [];
  for (const raw of problems) {
    const key = KNOWN.find(([re]) => re.test(raw.trim()))?.[1];
    const line = key ? t(key) : raw.trim();
    if (line && !out.includes(line)) out.push(line);
  }
  return out.join(" ");
}
