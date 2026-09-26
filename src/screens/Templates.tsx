import { ArrowsLeftRightIcon, ListChecksIcon, MicrophoneIcon, PencilSimpleIcon, PlusIcon, UserPlusIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar } from '../components/Avatar';
import { Button } from '../components/Button';
import { Dialog } from '../components/Dialog';
import { PersonProfileDialog } from '../components/PersonProfile';
import { Segmented } from '../components/Segmented';
import { TextField } from '../components/TextField';
import { useI18n } from '../i18n/I18nProvider';
import { AddParticipantModal } from './Participants';
import { useStore } from '../store/AppStore';
import { MEETING_TYPES, type MeetingType, type Person, type Template } from '../types';

/** Pick who takes a participant's place: someone not in the template yet, or a new person. */
function ReplacePersonDialog({ person, options, onPick, onNew, onClose }: { person: Person; options: Person[]; onPick: (id: string) => void; onNew: () => void; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Dialog title={t('templates.replaceTitle', { name: person.name })} onClose={onClose}>
      <p className="note">{options.length ? t('templates.replaceHint') : t('templates.noOthers')}</p>
      {options.length > 0 && (
        <ul className="replace-list">
          {options.map((p) => (
            <li key={p.id}>
              <button type="button" className="replace-list__item" onClick={() => onPick(p.id)}>
                <Avatar name={p.name} />
                <span className="who__text">
                  <span className="who__name">{p.name}</span>
                  {p.role && <span className="who__sub">{p.role}</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <Button icon={<UserPlusIcon size={20} aria-hidden />} onClick={onNew}>
        {t('templates.newPerson')}
      </Button>
    </Dialog>
  );
}

/** T02 — template editor, shown as a centred modal. */
function EditTemplatePanel({ template, onClose }: { template?: Template; onClose: () => void }) {
  const { t } = useI18n();
  const { account, people, resolvePerson, saveTemplate } = useStore();
  const [name, setName] = useState(template?.name ?? '');
  const [type, setType] = useState<MeetingType>(template?.type ?? 'medical');
  const [selected, setSelected] = useState<string[]>(template?.participantIds ?? people.map((p) => p.id));
  const [error, setError] = useState<string>();
  const [replacing, setReplacing] = useState<Person | null>(null);
  // 'add' = + button; a Person = "new person" chosen while replacing them.
  const [creating, setCreating] = useState<'add' | Person | null>(null);

  // Everyone in the directory plus anyone the template already references.
  const candidates = [...people.map((p) => p.id), ...(template?.participantIds ?? [])]
    .filter((id, i, a) => a.indexOf(id) === i)
    .map(resolvePerson)
    .filter((p): p is Person => !!p);

  const toggle = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const add = (id: string) => setSelected((s) => (s.includes(id) ? s : [...s, id]));
  // The newcomer takes the old participant's slot, so the template order is kept.
  const replace = (oldId: string, newId: string) =>
    setSelected((s) => (s.includes(newId) ? s.filter((x) => x !== oldId) : s.includes(oldId) ? s.map((x) => (x === oldId ? newId : x)) : [...s, newId]));

  const save = () => {
    if (!name.trim()) return setError(t('common.required'));
    saveTemplate({ id: template?.id, name: name.trim(), type, participantIds: selected });
    onClose();
  };

  return (
    <Dialog title={template ? t('templates.panelTitle') : t('templates.new')} onClose={onClose} wide>
      <TextField label={t('templates.name')} value={name} onChange={(e) => setName(e.target.value)} error={error} />
      <div className="field">
        <span className="field__label">{t('templates.type')}</span>
        <Segmented<MeetingType> label={t('templates.type')} variant="fill" value={type} onChange={setType} options={MEETING_TYPES.map((m) => ({ value: m, label: t(`typesShort.${m}`) }))} />
      </div>
      <fieldset className="tpl-people">
        <legend className="tpl-people__head">
          <span className="t-strong">{t('templates.participants')}</span>
          <span className="tpl-people__tools">
            <span className="note">{t('templates.selected', { n: selected.length, total: candidates.length })}</span>
            <button type="button" className="icon-btn" aria-label={t('templates.addPerson')} title={t('templates.addPerson')} onClick={() => setCreating('add')}>
              <PlusIcon size={20} aria-hidden />
            </button>
          </span>
        </legend>
        {candidates.map((p) => (
          <div key={p.id} className="tpl-person">
            <label className="tpl-person__main">
              <input type="checkbox" className="checkbox" checked={selected.includes(p.id)} onChange={() => toggle(p.id)} />
              <span className="t-strong">{p.name}</span>
              {p.id === account?.personId && <span className="tag tag--me">{t('common.me')}</span>}
              <span className="note truncate">{p.role}</span>
            </label>
            <button type="button" className="icon-btn" aria-label={t('templates.replace', { name: p.name })} title={t('templates.replace', { name: p.name })} onClick={() => setReplacing(p)}>
              <ArrowsLeftRightIcon size={20} aria-hidden />
            </button>
          </div>
        ))}
      </fieldset>
      <Button variant="primary" block onClick={save}>
        {t('templates.save')}
      </Button>

      {replacing && (
        <ReplacePersonDialog
          person={replacing}
          options={candidates.filter((p) => p.id !== replacing.id && !selected.includes(p.id))}
          onPick={(id) => (replace(replacing.id, id), setReplacing(null))}
          onNew={() => (setCreating(replacing), setReplacing(null))}
          onClose={() => setReplacing(null)}
        />
      )}
      {creating && (
        <AddParticipantModal
          title={creating === 'add' ? undefined : t('templates.replaceTitle', { name: creating.name })}
          onAdded={(id) => (creating === 'add' ? add(id) : replace(creating.id, id))}
          onClose={() => setCreating(null)}
        />
      )}
    </Dialog>
  );
}

/** Overlapping avatars + first names, so each template shows who it invites. */
function TemplatePeople({ ids }: { ids: string[] }) {
  const { t } = useI18n();
  const { account, resolvePerson } = useStore();
  const [profileId, setProfileId] = useState<string | null>(null);
  const people = ids.map(resolvePerson).filter((p): p is Person => !!p);
  const label = (p: Person) => (p.id === account?.personId ? t('common.meName', { name: p.name }) : p.name);
  const shown = people.slice(0, 2).map(label);
  const rest = people.length - shown.length;
  return (
    <div className="tpl-people-preview">
      {/* Hover or focus an avatar for the name; click opens the profile. */}
      <span className="avatar-stack">
        {people.slice(0, 5).map((p) => (
          <button key={p.id} type="button" className="avatar-tip" data-name={label(p)} aria-label={t('profile.open', { name: label(p) })} onClick={() => setProfileId(p.id)}>
            <Avatar name={p.name} />
          </button>
        ))}
      </span>
      <span className="note truncate">
        {shown.join(', ')}
        {rest > 0 && ` ${t('templates.more', { n: rest })}`}
      </span>
      {profileId && <PersonProfileDialog personId={profileId} onClose={() => setProfileId(null)} />}
    </div>
  );
}

/** T01 — Templates grid + T02 edit modal. */
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
