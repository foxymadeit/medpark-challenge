import { describe, expect, it } from "vitest";
import i18n from "../src/i18n/i18n";
describe("translations", () => {
  it("provides every interface key in EN, RO and RU", () => {
    // Plural forms differ by language (RU has one/few/many), so compare the
    // base keys and require each language's own CLDR "other" form.
    const base = (bundle: object) =>
      [
        ...new Set(
          Object.keys(bundle).map((k) =>
            k.replace(/_(zero|one|two|few|many|other)$/, ""),
          ),
        ),
      ].sort();
    const en = i18n.getResourceBundle("en", "translation");
    for (const language of ["ro", "ru"]) {
      const bundle = i18n.getResourceBundle(language, "translation");
      expect(base(bundle)).toEqual(base(en));
      for (const key of Object.keys(en).filter((k) => k.endsWith("_other")))
        expect(bundle[key]).toBeTruthy();
      for (const value of Object.values(bundle))
        expect(typeof value === "string" && value.length > 0).toBe(true);
    }
  });
});
