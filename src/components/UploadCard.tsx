import { CpuIcon, FileAudioIcon, UploadSimpleIcon, XIcon } from '@phosphor-icons/react';
import { useEffect, useRef, useState, type DragEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '../i18n/I18nProvider';
import { formatBytes } from '../lib/format';
import { useDraftMeeting } from '../lib/meeting';
import { ACCEPT, isAudio, readMinutes } from '../lib/upload';
import { useStore } from '../store/AppStore';
import { Button } from './Button';
import { ProgressBar } from './ProgressBar';

/** MOCK upload time: nothing leaves the browser, the bar just fills. */
const UPLOAD_MS = 2500;

type Picked = { file: File; minutes: number };

/**
 * The blue "Upload audio" card on New meeting. Click (or drop a file) → the file picker opens here,
 * the card fills while "uploading", then offers Write minutes. Same size in every state as the record card.
 */
export function UploadCard() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { createMeetingFromDraft } = useStore();
  const { title } = useDraftMeeting();
  const input = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<Picked | null>(null);
  const [progress, setProgress] = useState(0); // 0..1
  const [error, setError] = useState<string>();
  const [over, setOver] = useState(false);
  const uploading = !!picked && progress < 1;

  useEffect(() => {
    if (!picked || progress >= 1) return;
    const started = performance.now() - progress * UPLOAD_MS;
    const id = window.setInterval(() => setProgress(Math.min(1, (performance.now() - started) / UPLOAD_MS)), 50);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picked]);

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

  const meta = [picked.minutes ? t('common.minutes', { n: picked.minutes }) : '', formatBytes(picked.file.size)].filter(Boolean).join(' · ');

  return (
    <div className="start-tile start-tile--upload is-file" {...drop}>
      <div className="start-tile__top">
        <FileAudioIcon size={32} aria-hidden />
        {!uploading && (
          <Button
            variant="ink"
            icon={<CpuIcon size={20} aria-hidden />}
            onClick={() => {
              const id = createMeetingFromDraft('uploaded', picked.minutes, picked.file.name, title);
              navigate(`/processing/${id}`);
            }}
          >
            {t('upload.submit')}
          </Button>
        )}
      </div>
      <span className="start-tile__spacer" />
      <span className="t-h2">{uploading ? t('upload.uploading') : t('upload.uploaded')}</span>
      {uploading ? (
        <div className="start-tile__progress">
          <ProgressBar value={progress} label={t('upload.uploading')} />
        </div>
      ) : null}
      <span className="start-tile__file">
        <span className="truncate" title={picked.file.name}>
          {picked.file.name}
        </span>
        {!uploading && meta && <span className="start-tile__meta">· {meta}</span>}
        <button type="button" className="start-tile__remove" aria-label={uploading ? t('upload.cancel') : t('upload.remove', { name: picked.file.name })} onClick={clear}>
          <XIcon size={14} aria-hidden />
        </button>
      </span>
      {fileInput}
    </div>
  );
}
