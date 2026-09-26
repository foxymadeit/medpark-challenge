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
  // Approved here: shown as added at once (no flash back to Approve while the
  // list reloads) and kept in place, so the row does not jump.
  const [added, setAdded] = useState<Record<string, GlossaryCandidate["lang"]>>(
    {},
  );

  async function approve(c: GlossaryCandidate) {
    setBusy(keyOf(c));
    setError("");
    try {
      const lang = langs[keyOf(c)] ?? c.lang;
      await approveGlossaryCandidate({ ...c, lang });
      setAdded((a) => ({ ...a, [keyOf(c)]: lang }));
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
        <div className="table-scroll">
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
              {orderCandidates(
                data.map((c) =>
                  added[keyOf(c)] ? { ...c, approved: false } : c,
                ),
              )
                .map((c) =>
                  added[keyOf(c)]
                    ? { ...c, approved: true, lang: added[keyOf(c)] }
                    : c,
                )
                .map((c) => (
                  <tr key={keyOf(c)} className={c.approved ? "approved" : ""}>
                    <td>{c.heard}</td>
                    <td>
                      <strong>{c.corrected}</strong>
                    </td>
                    <td>{c.count}</td>
                    <td>
                      {c.approved ? (
                        // settled in the glossary: shown, no longer a choice
                        <span className="expand-in">
                          {c.lang.toUpperCase()}
                        </span>
                      ) : (
                        <select
                          aria-label={t("correctedLanguage")}
                          value={langs[keyOf(c)] ?? c.lang}
                          disabled={busy !== ""}
                          onChange={(e) =>
                            setLangs({
                              ...langs,
                              [keyOf(c)]: e.target
                                .value as GlossaryCandidate["lang"],
                            })
                          }
                        >
                          {LANGS.map((l) => (
                            <option key={l} value={l}>
                              {l.toUpperCase()}
                            </option>
                          ))}
                        </select>
                      )}
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
        </div>
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
