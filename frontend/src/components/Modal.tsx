import { useEffect, useRef, type ReactNode } from "react";
import { FiX as X } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { usePresence } from "../hooks/usePresence";
import Button from "./Button";

/** A centred dialog over a scrim. It fades in over 150 ms and out over
 * 120 ms (DESIGN.md), so it stays mounted briefly after `open` turns false;
 * Esc and the close button ask the owner to close rather than vanishing. */
export default function Modal({
  title,
  open = true,
  onClose,
  children,
}: {
  title: string;
  open?: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const { t } = useTranslation();
  const { present, closing } = usePresence(open, 120);
  useEffect(() => {
    const node = ref.current;
    if (!present || !node) return;
    if (!node.open) node.showModal();
    return () => node.close();
  }, [present]);
  if (!present) return null;
  return (
    <dialog
      className="edit-dialog"
      ref={ref}
      data-closing={closing || undefined}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <Button variant="quiet" aria-label={t("close")} onClick={onClose}>
          <X size={20} />
        </Button>
      </header>
      {children}
    </dialog>
  );
}
