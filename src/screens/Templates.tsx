import { ArrowsLeftRightIcon, CheckIcon, MicrophoneIcon, PlusIcon, UserPlusIcon, UsersThreeIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar } from '../components/Avatar';
import { Button } from '../components/Button';
import { Dialog } from '../components/Dialog';
import { PeopleStack } from '../components/PeopleStack';
import { MeetingTypeIcon } from '../components/MeetingTypeIcon';
import { Segmented } from '../components/Segmented';
import { TemplateBadge } from '../components/TemplateBadge';
import { TextField } from '../components/TextField';
import { useI18n } from '../i18n/I18nProvider';
import { COLOR_KEYS, PALETTE, templateColor, type ColorKey } from '../lib/colors';
import { AddParticipantModal } from './Participants';
import { Highlight } from '../components/ParticipantsField';
import { isEmail } from '../lib/format';
import { suggestByName } from '../lib/participants';
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
  const { account, people, resolvePerson, saveTemplate, deleteTemplate, addPerson } = useStore();
  const [name, setName] = useState(template?.name ?? '');
  const [type, setType] = useState<MeetingType>(template?.type ?? 'medical');
  const [color, setColor] = useState<ColorKey>(template ? templateColor(template) : 'blue');
  // A new template starts with just you; the list shows only who's in the template.
  const [selected, setSelected] = useState<string[]>(template?.participantIds ?? (account ? [account.personId] : []));
  const [error, setError] = useState<string>();
  const [replacing, setReplacing] = useState<Person | null>(null);
  const [creating, setCreating] = useState<Person | null>(null); // "new person" chosen while replacing someone
  const [confirmDelete, setConfirmDelete] = useState(false);

  const members = selected.map(resolvePerson).filter((p): p is Person => !!p);
  const others = [...people, ...(template?.participantIds ?? []).map(resolvePerson).filter((p): p is Person => !!p)].filter((p, i, a) => a.findIndex((x) => x.id === p.id) === i && !selected.includes(p.id));

  // Unticking removes them from the template (and from this list).
  const remove = (id: string) => setSelected((s) => s.filter((x) => x !== id));
  const add = (id: string) => setSelected((s) => (s.includes(id) ? s : [...s, id]));
  // The newcomer takes the old participant's slot, so the template order is kept.
  const replace = (oldId: string, newId: string) =>
    setSelected((s) => (s.includes(newId) ? s.filter((x) => x !== oldId) : s.includes(oldId) ? s.map((x) => (x === oldId ? newId : x)) : [...s, newId]));

  // "+ Add participant": a search over saved participants (by first name / surname), or a new name, or just an email (a guest).
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [addError, setAddError] = useState<string>();
  const q = query.trim();
  const matches = q.includes('@') ? others.filter((p) => p.email?.toLowerCase().startsWith(q.toLowerCase())).slice(0, 5) : suggestByName(others, q, () => false, 5);
  const exact = [...people, ...members].some((p) => p.name.toLowerCase() === q.toLowerCase() || p.email?.toLowerCase() === q.toLowerCase());
  const canCreate = !!q && !exact;
  const closeAdd = () => (setAdding(false), setQuery(''), setActive(0), setAddError(undefined));
  const pickExisting = (id: string) => (add(id), setQuery(''), setActive(0));
  const createTyped = () => {
    if (q.includes('@')) {
      if (!isEmail(q)) return setAddError(t('common.emailInvalid'));
      add(addPerson({ name: q, email: q, role: '', access: 'receives' })); // guest: just an email
    } else add(addPerson({ name: q, role: '', access: 'receives' }));
    setQuery('');
    setActive(0);
  };

  const initial = template?.participantIds ?? (account ? [account.personId] : []);
  const dirty =
    name.trim() !== (template?.name ?? '') ||
    type !== (template?.type ?? 'medical') ||
    color !== (template ? templateColor(template) : 'blue') ||
    selected.length !== initial.length ||
    selected.some((id, i) => id !== initial[i]);

  const save = () => {
    if (!name.trim()) return setError(t('common.required'));
    saveTemplate({ id: template?.id, name: name.trim(), type, color, participantIds: selected });
    onClose();
  };

  return (
    <Dialog title={template ? t('templates.panelTitle') : t('templates.new')} onClose={onClose} wide>
      <TextField editable label={t('templates.name')} value={name} onChange={(e) => (setName(e.target.value), setError(undefined))} error={error} />
      <div className="field">
        <span className="field__label">{t('templates.type')}</span>
        <Segmented<MeetingType> label={t('templates.type')} variant="fill" value={type} onChange={setType} options={MEETING_TYPES.map((m) => ({ value: m, label: t(`typesShort.${m}`), icon: <MeetingTypeIcon type={m} /> }))} />
      </div>
      <div className="field">
        <span className="field__label" id="tpl-color">
          {t('templates.color')}
        </span>
        <div className="swatches" role="radiogroup" aria-labelledby="tpl-color">
          {COLOR_KEYS.map((c) => (
            <button
              key={c}
              type="button"
              role="radio"
              aria-checked={color === c}
              aria-label={t(`colors.${c}`)}
              title={t(`colors.${c}`)}
              className="swatch"
              style={{ background: PALETTE[c].solid, color: 'var(--sm-on-solid)' }}
              onClick={() => setColor(c)}
            >
              {color === c && <CheckIcon size={16} weight="bold" aria-hidden />}
            </button>
          ))}
        </div>
      </div>
      <fieldset className="tpl-people">
        <legend className="tpl-people__head">
          <span className="row" style={{ gap: 8 }}>
            <UsersThreeIcon size={20} aria-hidden />
            <span className="t-strong">{t('templates.participants')}</span>
          </span>
          <span className="note">{t('common.participantsCount', { count: members.length })}</span>
        </legend>
        {/* Only who's in the template; untick to take them out. */}
        {members.map((p) => (
          <div key={p.id} className="tpl-person">
            <label className="tpl-person__main">
              <input type="checkbox" className="checkbox" checked onChange={() => remove(p.id)} aria-label={t('templates.removeFrom', { name: p.name })} />
              <Avatar name={p.name} />
              <span className="t-strong">{p.name}</span>
              {p.id === account?.personId && <span className="tag tag--me">{t('common.me')}</span>}
              <span className="note truncate">{p.role || p.email}</span>
            </label>
            <button type="button" className="icon-btn" aria-label={t('templates.replace', { name: p.name })} title={t('templates.replace', { name: p.name })} onClick={() => setReplacing(p)}>
              <ArrowsLeftRightIcon size={20} aria-hidden />
            </button>
          </div>
        ))}
        {/* Add row: the + sits in the avatars' column. */}
        <div className="tpl-person tpl-person--new">
          <span className="tpl-person__plus" aria-hidden>
            <PlusIcon size={16} weight="bold" />
          </span>
          {adding ? (
            <input
              autoFocus
              className="tpl-person__input"
              placeholder={t('recipients.ph')}
              aria-label={t('templates.addPerson')}
              role="combobox"
              aria-expanded={!!q}
              aria-controls="tpl-suggest"
              aria-autocomplete="list"
              aria-activedescendant={q ? `tpl-opt-${active}` : undefined}
              aria-invalid={addError ? true : undefined}
              value={query}
              onChange={(e) => (setQuery(e.target.value), setActive(0), setAddError(undefined))}
              onBlur={() => !q && closeAdd()}
              onKeyDown={(e) => {
                const count = matches.length + (canCreate ? 1 : 0);
                if (e.key === 'ArrowDown') (e.preventDefault(), setActive((a) => Math.min(a + 1, count - 1)));
                else if (e.key === 'ArrowUp') (e.preventDefault(), setActive((a) => Math.max(a - 1, 0)));
                else if (e.key === 'Escape') (e.stopPropagation(), closeAdd());
                else if (e.key === 'Enter') {
                  e.preventDefault();
                  if (matches[active]) pickExisting(matches[active].id);
                  else if (canCreate) createTyped();
                }
              }}
            />
          ) : (
            <button type="button" className="link-btn tpl-person__add" onClick={() => setAdding(true)}>
              {t('templates.addPerson')}
            </button>
          )}
        </div>
        {addError && <p className="field__error tpl-person__error">{addError}</p>}
        {/* Saved participants first, "add new" last. Inline so the modal never clips it. */}
        {adding && q && (matches.length > 0 || canCreate) && (
          <ul id="tpl-suggest" role="listbox" aria-label={t('templates.addPerson')} className="tpl-suggest">
            {matches.map((p, i) => (
              <li key={p.id} id={`tpl-opt-${i}`} role="option" aria-selected={i === active} className={`tpl-suggest__option${i === active ? ' is-active' : ''}`} onMouseEnter={() => setActive(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => pickExisting(p.id)}>
                <Avatar name={p.name} />
                <span className="who__text">
                  <span className="who__name truncate">{q.includes('@') ? p.name : <Highlight text={p.name} query={q.toLowerCase()} />}</span>
                  <span className="who__sub truncate">{[p.role, p.email].filter(Boolean).join(' · ')}</span>
                </span>
              </li>
            ))}
            {canCreate && (
              <li id={`tpl-opt-${matches.length}`} role="option" aria-selected={active === matches.length} className={`tpl-suggest__option tpl-suggest__create${active === matches.length ? ' is-active' : ''}`} onMouseEnter={() => setActive(matches.length)} onMouseDown={(e) => e.preventDefault()} onClick={createTyped}>
                <span className="tpl-person__plus" aria-hidden style={{ marginLeft: 0 }}>
                  <PlusIcon size={16} weight="bold" />
                </span>
                <span className="who__name truncate">{q.includes('@') ? t('owner.addEmail', { email: q }) : t('owner.addName', { name: q })}</span>
              </li>
            )}
          </ul>
        )}
      </fieldset>
      <div className="tpl-editor__actions">
        {template && (
          <Button variant="ghost" className="btn--danger-text" onClick={() => setConfirmDelete(true)}>
            {t('templates.delete')}
          </Button>
        )}
        <Button variant="primary" disabled={!dirty} onClick={save} className="tpl-editor__save">
          {template ? t('templates.saveChanges') : t('templates.save')}
        </Button>
      </div>

      {confirmDelete && template && (
        <Dialog title={t('templates.deleteTitle')} onClose={() => setConfirmDelete(false)}>
          <p className="lead">{t('templates.deleteLead')}</p>
          <div className="row" style={{ justifyContent: 'flex-end', gap: 12 }}>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="danger" onClick={() => (deleteTemplate(template.id), setConfirmDelete(false), onClose())}>
              {t('templates.deleteConfirm')}
            </Button>
          </div>
        </Dialog>
      )}
      {replacing && (
        <ReplacePersonDialog
          person={replacing}
          options={others}
          onPick={(id) => (replace(replacing.id, id), setReplacing(null))}
          onNew={() => (setCreating(replacing), setReplacing(null))}
          onClose={() => setReplacing(null)}
        />
      )}
      {creating && <AddParticipantModal title={t('templates.replaceTitle', { name: creating.name })} onAdded={(id) => replace(creating.id, id)} onClose={() => setCreating(null)} />}
    </Dialog>
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
      <div className="page__head page__head--row" style={{ marginBottom: 40 }}>
        <div className="page__head">
          <h1 className="t-h1">{t('templates.title')}</h1>
          <p className="lead">{t('templates.lead')}</p>
        </div>
        <Button variant="ink" icon={<PlusIcon size={20} aria-hidden />} onClick={() => setEditing('new')}>
          {t('templates.new')}
        </Button>
      </div>
      <ul className="tpl-grid">
        {templates.map((tpl) => (
          <li key={tpl.id} className="card card--pad tpl-card">
            <div className="tpl-card__head">
              <TemplateBadge color={templateColor(tpl)} type={tpl.type} />
              <div className="stack" style={{ gap: 4, minWidth: 0 }}>
                <h2 className="t-h3">{tpl.name}</h2>
                <p className="note">{t('templates.meta', { type: t(`typesShort.${tpl.type}`), count: tpl.participantIds.length })}</p>
              </div>
            </div>
            <div className="tpl-card__actions">
              <PeopleStack ids={tpl.participantIds} />
              <Button variant="ghost" className="tpl-card__edit" aria-label={t('templates.editLabel', { name: tpl.name })} onClick={() => setEditing(tpl)}>
                {t('templates.edit')}
              </Button>
              <Button
                icon={<MicrophoneIcon size={20} aria-hidden />}
                aria-label={t('templates.startLabel', { name: tpl.name })}
                onClick={() => {
                  setDraft({ templateId: tpl.id, type: tpl.type, participants: undefined }); // the template's people fill the list
                  navigate('/new');
                }}
              >
                {t('templates.start')}
              </Button>
            </div>
          </li>
        ))}
      </ul>
      {editing && <EditTemplatePanel template={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
