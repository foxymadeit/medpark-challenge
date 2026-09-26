import { CpuIcon, FileAudioIcon, UploadSimpleIcon, XIcon } from '@phosphor-icons/react';
import { useRef, useState, type DragEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { useI18n } from '../i18n/I18nProvider';
import { formatBytes } from '../lib/format';
import { useDraftMeeting } from '../lib/meeting';
import { useStore } from '../store/AppStore';

const ACCEPT = '.wav,.mp3,.m4a,audio/wav,audio/mpeg,audio/mp4,audio/x-m4a';
const isAudio = (f: File) => /\.(wav|mp3|m4a)$/i.test(f.name) || /^audio\//.test(f.type);

/** Read duration (minutes) from the file's metadata. */
function readMinutes(file: File): Promise<number> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const audio = new Audio();
    audio.preload = 'metadata';
    audio.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      resolve(Number.isFinite(audio.duration) ? Math.max(1, Math.round(audio.duration / 60)) : 0);
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(0);
    };
    audio.src = url;
  });
}

/** 03 — Upload audio. */
export function Upload() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { createMeetingFromDraft } = useStore();
  const { title, typeLabel, count } = useDraftMeeting();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<{ file: File; minutes: number } | null>(null);
  const [error, setError] = useState<string>();
  const [over, setOver] = useState(false);

  const take = async (f?: File) => {
    if (!f) return;
    if (!isAudio(f)) return setError(t('upload.wrongType'));
    setError(undefined);
    setFile({ file: f, minutes: await readMinutes(f) });
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    void take(e.dataTransfer.files[0]);
  };

  const submit = () => {
    if (!file) return;
    const id = createMeetingFromDraft('uploaded', file.minutes, file.file.name);
    navigate(`/processing/${id}`);
  };

  return (
    <div className="page upload">
      <div className="upload__column">
        <div className="page__head">
          <h1 className="t-h1">{t('upload.title')}</h1>
          <p className="lead">
            {title} · {typeLabel} · {t('common.participantsCount', { count })}
          </p>
        </div>
        <button
          type="button"
          className={`dropzone${over ? ' is-over' : ''}`}
          onClick={() => input.current?.click()}
          onDragOver={(e) => (e.preventDefault(), setOver(true))}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
          aria-describedby={error ? 'upload-err' : undefined}
        >
          <UploadSimpleIcon size={32} aria-hidden />
          <span className="t-strong">{t('upload.drop')}</span>
          <span className="note">{t('upload.hint')}</span>
        </button>
        <input ref={input} type="file" accept={ACCEPT} hidden onChange={(e) => void take(e.target.files?.[0])} />
        {error && (
          <p id="upload-err" className="field__error" role="alert">
            {error}
          </p>
        )}
        {file && (
          <div className="tile file-row">
            <FileAudioIcon size={20} aria-hidden />
            <span className="who__text" style={{ flex: 1 }}>
              <span className="who__name truncate">{file.file.name}</span>
              <span className="t-data-sm c-secondary">
                {file.minutes ? `${t('common.minutes', { n: file.minutes })} · ` : ''}
                {formatBytes(file.file.size)}
              </span>
            </span>
            <button type="button" className="icon-btn" aria-label={t('upload.remove', { name: file.file.name })} onClick={() => setFile(null)}>
              <XIcon size={16} aria-hidden />
            </button>
          </div>
        )}
      </div>
      <div className="page__actions">
        <Button variant="primary" icon={<CpuIcon size={20} aria-hidden />} disabled={!file} onClick={submit}>
          {t('upload.submit')}
        </Button>
      </div>
    </div>
  );
}
