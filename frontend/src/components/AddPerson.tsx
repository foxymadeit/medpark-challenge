import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Participant } from "../types/meeting";
import { addPerson } from "../api/meetings";
import Modal from "./Modal";
import InputField from "./InputField";
import Button from "./Button";
export default function AddPerson({
  onClose,
  onAdded,
}: {
  onClose: () => void;
  onAdded: (p: Participant) => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Modal title={t("add")} onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            onAdded(
              await addPerson({ name, email: email.trim() || undefined }),
            );
          } catch {
            setError("requestFailed");
          } finally {
            setBusy(false);
          }
        }}
      >
        <InputField
          label={t("name")}
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <InputField
          label={t("email")}
          type="email"
          maxLength={254}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        {error && <p className="error">{t(error)}</p>}
        <div className="button-row">
          <Button
            type="submit"
            variant="primary"
            disabled={busy || !name.trim()}
          >
            {t("add")}
          </Button>
          <Button onClick={onClose}>{t("cancel")}</Button>
        </div>
      </form>
    </Modal>
  );
}
