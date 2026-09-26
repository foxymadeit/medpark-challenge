import { useTranslation } from "react-i18next";
import { documentUrl } from "../api/meetings";
import type { Meeting } from "../types/meeting";
import { LANGUAGE_NAMES as NAMES } from "../utils";

/** Figma M02: the server-rendered minutes, one PDF and one DOCX per
 * language, with how many items were checked against the transcript. */
export default function DocumentsCard({ meeting }: { meeting: Meeting }) {
  const { t } = useTranslation();
  const langs = meeting.documents ?? [];
  if (!langs.length) return null;
  return (
    <section className="panel documents-card" aria-labelledby="docs-title">
      <h2 id="docs-title">{t("documents")}</h2>
      <ul className="documents-list">
        {langs.map((lang) => (
          <li key={lang} lang={lang}>
            <span>{NAMES[lang]}</span>
            <div className="button-row">
              <a
                className="button secondary compact"
                href={documentUrl(meeting.id, lang, "pdf")}
                download
                aria-label={`PDF, ${NAMES[lang]}`}
              >
                PDF
              </a>
              <a
                className="button secondary compact"
                href={documentUrl(meeting.id, lang, "docx")}
                download
                aria-label={`DOCX, ${NAMES[lang]}`}
              >
                DOCX
              </a>
            </div>
          </li>
        ))}
      </ul>
      {meeting.checked && (
        <>
          <hr />
          <p className="muted">{t("checkedAgainst")}</p>
          <p className="mono">
            {t("checkedCount", {
              verified: meeting.checked.verified,
              total: meeting.checked.total,
            })}
          </p>
        </>
      )}
      <p className="muted small">{t("aiDrafted")}</p>
    </section>
  );
}
