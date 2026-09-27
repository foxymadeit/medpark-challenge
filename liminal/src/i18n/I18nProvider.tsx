import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { en } from './en';
import ro from './ro.json';
import ru from './ru.json';

export type Lang = 'en' | 'ro' | 'ru';
export const LANGS: Lang[] = ['en', 'ro', 'ru'];

const dictionaries: Record<Lang, Record<string, unknown>> = { en, ro, ru };
const STORAGE_KEY = 'liminal:lang';

/** Resolve "a.b.c" in a nested dictionary. */
function lookup(dict: Record<string, unknown>, key: string): string | undefined {
  const value = key.split('.').reduce<unknown>(
    (node, part) => (node && typeof node === 'object' ? (node as Record<string, unknown>)[part] : undefined),
    dict,
  );
  return typeof value === 'string' ? value : undefined;
}

type Vars = Record<string, string | number>;
type I18n = { lang: Lang; setLang: (l: Lang) => void; t: (key: string, vars?: Vars) => string };

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Lang | null;
      return saved && LANGS.includes(saved) ? saved : 'en';
    } catch {
      return 'en';
    }
  });

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* storage unavailable — keep in memory */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const t = useCallback(
    (key: string, vars?: Vars) => {
      // Plurals: with a numeric {count}, try `key_<CLDR category>` first (one / few / many / other),
      // e.g. RU "5 участников" = participantsCount_many. Falls back to the plain key.
      const pick = (l: Lang) => {
        const cat = typeof vars?.count === 'number' ? new Intl.PluralRules(l).select(vars.count) : null;
        for (const k of cat ? [`${key}_${cat}`, key] : [key]) {
          const v = lookup(dictionaries[l], k);
          if (v && v !== 'TODO') return v;
        }
        return undefined;
      };
      // Untranslated (missing / "TODO") strings fall back to English.
      let str = pick(lang) ?? pick('en');
      if (str === undefined) {
        if (import.meta.env.DEV) console.warn(`[i18n] missing key: ${key}`);
        return key;
      }
      if (vars) for (const [k, v] of Object.entries(vars)) str = str.replaceAll(`{${k}}`, String(v));
      return str;
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used inside <I18nProvider>');
  return ctx;
}
