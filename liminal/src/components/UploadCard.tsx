import { UploadSimpleIcon } from '@phosphor-icons/react';
import { useRef, useState, type DragEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '../i18n/I18nProvider';
import { ACCEPT, handOffUpload, isAudio, readMinutes } from '../lib/upload';

/**
 * The blue "Upload audio" card on New meeting. Click (or drop a file) → the file picker opens here,
 * then the Upload screen shows the file uploading, with Change file and Write minutes.
 */
export function UploadCard() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string>();
  const [over, setOver] = useState(false);

  const take = async (f?: File) => {
    if (!f) return;
    if (!isAudio(f)) return setError(t('upload.wrongType'));
    handOffUpload({ file: f, minutes: await readMinutes(f) });
    navigate('/upload');
  };

  const drop = {
    onDragOver: (e: DragEvent) => (e.preventDefault(), setOver(true)),
    onDragLeave: () => setOver(false),
    onDrop: (e: DragEvent) => {
      e.preventDefault();
      setOver(false);
      void take(e.dataTransfer.files[0]);
    },
  };

  const fileInput = <input ref={input} type="file" accept={ACCEPT} hidden onChange={(e) => void take(e.target.files?.[0])} />;

  return (
    <>
      <button type="button" className={`start-tile start-tile--upload${over ? ' is-over' : ''}`} onClick={() => input.current?.click()} {...drop}>
        <UploadSimpleIcon size={32} aria-hidden />
        <span className="start-tile__spacer" />
        <span className="t-h2">{t('newMeeting.upload')}</span>
        <span className={`note${error ? ' c-danger' : ''}`} role={error ? 'alert' : undefined}>
          {error ?? t('newMeeting.uploadHint')}
        </span>
      </button>
      {fileInput}
    </>
  );
}
