import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  approveGlossaryCandidate,
  getGlossaryCandidates,
  orderCandidates,
  type GlossaryCandidate,
} from "../api/meetings";
import { useData } from "../hooks/useData";
import Button from "./Button";

const LANGS = ["ro", "ru", "en"] as const;
const keyOf = (c: GlossaryCandidate) => `${c.heard}\n${c.corrected}`;

/** Admin: words people corrected in the minutes, to add to the site glossary. */
export default function CorrectedWords() {
  const { t } = useTranslation();
  const { data, refresh } = useData(getGlossaryCandidates, 30000);
  const [langs, setLangs] = useState<Record<string, GlossaryCandidate["lang"]>>(
    {},
  );
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function approve(c: GlossaryCandidate) {
    setBusy(keyOf(c));
    setError("");
    try {
      await approveGlossaryCandidate({ ...c, lang: langs[keyOf(c)] ?? c.lang });
      refresh();
    } catch {
      setError(t("requestFailed"));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="panel minutes-card corrected-words">
      <h2>{t("correctedWords")}</h2>
      <p className="muted">{t("correctedWordsIntro")}</p>
      {data?.length ? (
        <table>
          <thead>
            <tr>
              <th>{t("correctedHeard")}</th>
              <th>{t("correctedTo")}</th>
              <th>{t("correctedCount")}</th>
              <th>{t("correctedLanguage")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {orderCandidates(data).map((c) => (
              <tr key={keyOf(c)} className={c.approved ? "approved" : ""}>
                <td>{c.heard}</td>
                <td>
                  <strong>{c.corrected}</strong>
                </td>
                <td>{c.count}</td>
                <td>
                  <select
                    aria-label={t("correctedLanguage")}
                    value={langs[keyOf(c)] ?? c.lang}
                    disabled={c.approved}
                    onChange={(e) =>
                      setLangs({
                        ...langs,
                        [keyOf(c)]: e.target.value as GlossaryCandidate["lang"],
                      })
                    }
                  >
                    {LANGS.map((l) => (
                      <option key={l} value={l}>
                        {l.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  {c.approved ? (
                    <span className="success">{t("correctedAdded")}</span>
                  ) : (
                    <Button
                      disabled={busy !== ""}
                      onClick={() => void approve(c)}
                    >
                      {busy === keyOf(c)
                        ? t("correctedAdding")
                        : t("correctedApprove")}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>{t("correctedEmpty")}</p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
