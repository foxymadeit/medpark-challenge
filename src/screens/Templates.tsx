import { ListChecksIcon, MicrophoneIcon, PencilSimpleIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar } from '../components/Avatar';
import { Button } from '../components/Button';
import { Dialog } from '../components/Dialog';
import { Segmented } from '../components/Segmented';
import { TextField } from '../components/TextField';
import { useI18n } from '../i18n/I18nProvider';
import { useStore } from '../store/AppStore';
import { MEETING_TYPES, type MeetingType, type Person, type Template } from '../types';

function EditTemplatePanel({ template, onClose }: { template?: Template; onClose: () => void }) {
  const { t } = useI18n();
  const { people, resolvePerson, saveTemplate } = useStore();
  const [name, setName] = useState(template?.name ?? '');
  const [type, setType] = useState<MeetingType>(template?.type ?? 'medical');
  const [selected, setSelected] = useState<string[]>(template?.participantIds ?? people.map((p) => p.id));
  const [error, setError] = useState<string>();

  // Everyone in the directory plus anyone the template already references.
  const candidates = [...people.map((p) => p.id), ...(template?.participantIds ?? [])]
    .filter((id, i, a) => a.indexOf(id) === i)
    .map(resolvePerson)
    .filter((p): p is Person => !!p);

  const toggle = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const save = () => {
    if (!name.trim()) return setError(t('common.required'));
    saveTemplate({ id: template?.id, name: name.trim(), type, participantIds: selected });
    onClose();
  };

  return (
    <Dialog title={template ? t('templates.panelTitle') : t('templates.new')} onClose={onClose} variant="panel">
      <TextField label={t('templates.name')} value={name} onChange={(e) => setName(e.target.value)} error={error} />
      <div className="field">
        <span className="field__label">{t('templates.type')}</span>
        <Segmented<MeetingType> label={t('templates.type')} variant="fill" value={type} onChange={setType} options={MEETING_TYPES.map((m) => ({ value: m, label: t(`typesShort.${m}`) }))} />
      </div>
      <fieldset className="tpl-people">
        <legend className="tpl-people__head">
          <span className="t-strong">{t('templates.participants')}</span>
          <span className="note">{t('templates.selected', { n: selected.length, total: candidates.length })}</span>
        </legend>
        {candidates.map((p) => (
          <label key={p.id} className="tpl-person">
            <input type="checkbox" className="checkbox" checked={selected.includes(p.id)} onChange={() => toggle(p.id)} />
            <span className="t-strong">{p.name}</span>
            <span className="note">{p.role}</span>
          </label>
        ))}
      </fieldset>
      <span style={{ flex: 1 }} />
      <Button variant="primary" block onClick={save}>
        {t('templates.save')}
      </Button>
    </Dialog>
  );
}

/** Overlapping avatars + first names, so each template shows who it invites. */
function TemplatePeople({ ids }: { ids: string[] }) {
  const { t } = useI18n();
  const { resolvePerson } = useStore();
  const people = ids.map(resolvePerson).filter((p): p is Person => !!p);
  const shown = people.slice(0, 2).map((p) => p.name);
  const rest = people.length - shown.length;
  return (
    <div className="tpl-people-preview" title={people.map((p) => p.name).join(', ')}>
      <span className="avatar-stack" aria-hidden>
        {people.slice(0, 5).map((p) => (
          <Avatar key={p.id} name={p.name} />
        ))}
      </span>
      <span className="note truncate">
        <span className="sr-only">{t('templates.participants')}: </span>
        {shown.join(', ')}
        {rest > 0 && ` ${t('templates.more', { n: rest })}`}
      </span>
    </div>
  );
}

/** T01 — Templates grid + T02 edit side panel. */
export function Templates() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { templates, setDraft } = useStore();
  const [editing, setEditing] = useState<Template | 'new' | null>(null);

  return (
    <div className="page">
      <div className="page__head" style={{ marginBottom: 40 }}>
        <h1 className="t-h1">{t('templates.title')}</h1>
        <p className="lead">{t('templates.lead')}</p>
      </div>
      <ul className="tpl-grid">
        {templates.map((tpl) => (
          <li key={tpl.id} className="card card--pad tpl-card">
            <div className="stack" style={{ gap: 4 }}>
              <h2 className="t-h3">{tpl.name}</h2>
              <p className="note">{t('templates.meta', { type: t(`typesShort.${tpl.type}`), count: tpl.participantIds.length })}</p>
            </div>
            <div className="tpl-card__actions">
              <TemplatePeople ids={tpl.participantIds} />
              <Button variant="ghost" icon={<PencilSimpleIcon size={20} aria-hidden />} aria-label={t('templates.editLabel', { name: tpl.name })} onClick={() => setEditing(tpl)}>
                {t('templates.edit')}
              </Button>
              <Button
                icon={<MicrophoneIcon size={20} aria-hidden />}
                aria-label={t('templates.startLabel', { name: tpl.name })}
                onClick={() => {
                  setDraft({ templateId: tpl.id, type: tpl.type });
                  navigate('/new');
                }}
              >
                {t('templates.start')}
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <div className="page__actions">
        <Button variant="primary" icon={<ListChecksIcon size={20} aria-hidden />} onClick={() => setEditing('new')}>
          {t('templates.new')}
        </Button>
      </div>
      {editing && <EditTemplatePanel template={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
