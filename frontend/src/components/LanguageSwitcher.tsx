import { useTranslation } from "react-i18next";
export default function LanguageSwitcher() {
  const { i18n } = useTranslation();
  return (
    <div className="language-switcher">
      {["en", "ro", "ru"].map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-label={{ en: "English", ro: "Română", ru: "Русский" }[l]}
          aria-pressed={i18n.resolvedLanguage === l}
          onClick={() => void i18n.changeLanguage(l)}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
