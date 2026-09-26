import { useState } from "react";
import { FiCheckCircle, FiMail, FiCopy } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { markReviewed, saveMeetingAsTemplate } from "../api/meetings";
import { useAuth } from "../auth/useAuth";
import { notifyUpdate } from "../hooks/useData";
import type { Meeting } from "../types/meeting";
import Button from "./Button";

export default function ManualReviewBar({ meeting }: { meeting: Meeting }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const reviewed = meeting.reviewState === "reviewed";
  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      notifyUpdate();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "requestFailed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel manual-review-bar">
      <div>
        {meeting.deliveryState === "stopped" && !reviewed && (
          <p className="stopped-note" role="status">
            {t("sendingStopped")}
          </p>
        )}
        <strong>
          {t(reviewed ? "reviewComplete" : "reviewBeforeSending")}
        </strong>
        <p>{t(reviewed ? "readyToSendDetail" : "reviewChecklist")}</p>
      </div>
      <div className="button-row">
        {!reviewed && (
          <Button
            disabled={busy}
            onClick={() => void run(() => markReviewed(meeting.id))}
          >
            <FiCheckCircle /> {t("markReviewComplete")}
          </Button>
        )}
        <Button
          variant="primary"
          disabled={busy || !reviewed || meeting.status === "sending"}
          onClick={() => navigate(`/meetings/${meeting.id}/email`)}
        >
          <FiMail /> {t("previewEmail")}
        </Button>
        {reviewed && user?.role === "admin" && (
          <Button
            disabled={busy}
            onClick={() => {
              setBusy(true);
              setError("");
              void saveMeetingAsTemplate(meeting, user.role)
                .then((template) => navigate(`/templates/${template.id}/edit`))
                .catch((reason: unknown) =>
                  setError(
                    reason instanceof Error ? reason.message : "requestFailed",
                  ),
                )
                .finally(() => setBusy(false));
            }}
          >
            <FiCopy /> {t("saveAsTemplate")}
          </Button>
        )}
      </div>
      {error && (
        <p className="error" role="alert">
          {t(error, { defaultValue: t("requestFailed") })}
        </p>
      )}
    </section>
  );
}
