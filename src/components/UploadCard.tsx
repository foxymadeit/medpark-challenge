import { FileAudioIcon, UploadSimpleIcon, XIcon } from '@phosphor-icons/react';
import { useEffect, useRef, useState, type DragEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '../i18n/I18nProvider';
import { ACCEPT, handOffUpload, isAudio, readMinutes } from '../lib/upload';
import { ProgressBar } from './ProgressBar';

/** MOCK upload time: nothing leaves the browser, the bar just fills. */
const UPLOAD_MS = 2500;

type Picked = { file: File; minutes: number };

/**
 * The blue "Upload audio" card on New meeting. Click (or drop a file) → the file picker opens here,
 * the card fills while "uploading", then the Upload screen shows the file with Write minutes. Same size in every state as the record card.
 */
export function UploadCard() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<Picked | null>(null);
  const [progress, setProgress] = useState(0); // 0..1
  const [error, setError] = useState<string>();
  const [over, setOver] = useState(false);

  useEffect(() => {
    if (!picked) return;
    if (progress >= 1) {
      handOffUpload(picked);
      navigate('/upload');
      return;
    }
    const started = performance.now() - progress * UPLOAD_MS;
    const id = window.setInterval(() => setProgress(Math.min(1, (performance.now() - started) / UPLOAD_MS)), 50);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picked, progress >= 1]);

  const take = async (f?: File) => {
    if (!f) return;
    if (!isAudio(f)) return setError(t('upload.wrongType'));
    setError(undefined);
    setProgress(0);
    setPicked({ file: f, minutes: await readMinutes(f) });
  };

  const clear = () => {
    setPicked(null);
    setProgress(0);
    if (input.current) input.current.value = '';
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

  if (!picked) {
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

  // Uploading: the card fills, then the Upload screen opens with the file (review / change it before processing).
  return (
    <div className="start-tile start-tile--upload is-file">
      <FileAudioIcon size={32} aria-hidden />
      <span className="start-tile__spacer" />
      <span className="t-h2">{t('upload.uploading')}</span>
      <div className="start-tile__progress">
        <ProgressBar value={progress} label={t('upload.uploading')} />
      </div>
      <span className="start-tile__file">
        <span className="truncate" title={picked.file.name}>
          {picked.file.name}
        </span>
        <button type="button" className="start-tile__remove" aria-label={t('upload.cancel')} onClick={clear}>
          <XIcon size={14} aria-hidden />
        </button>
      </span>
    </div>
  );
}
