import { useEffect, useRef, type ReactNode } from "react";
import { FiX as X } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import Button from "./Button";
export default function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const { t } = useTranslation();
  useEffect(() => {
    const node = ref.current;
    node?.showModal();
    return () => node?.close();
  }, []);
  return (
    <dialog className="edit-dialog" ref={ref} onCancel={onClose}>
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
