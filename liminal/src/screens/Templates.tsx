import { ArrowsLeftRightIcon, CheckIcon, MicrophoneIcon, PencilSimpleIcon, PlusIcon, UserPlusIcon, UsersThreeIcon } from '@phosphor-icons/react';
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
  const { account, people, resolvePerson, saveTemplate, addPerson } = useStore();
  const [newName, setNewName] = useState('');
  const [name, setName] = useState(template?.name ?? '');
  const [type, setType] = useState<MeetingType>(template?.type ?? 'medical');
  const [color, setColor] = useState<ColorKey>(template ? templateColor(template) : 'blue');
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

  // Placeholder row at the bottom: type a name, Enter adds and ticks them. Details can be filled on Participants.
  // Predictive: unticked people whose name, role or email contains what's typed.
  const [active, setActive] = useState(0);
  const q = newName.trim().toLowerCase();
  const matches = q ? candidates.filter((p) => !selected.includes(p.id) && [p.name, p.role, p.email].some((v) => v?.toLowerCase().includes(q))).slice(0, 5) : [];
  const pickExisting = (id: string) => (add(id), setNewName(''), setActive(0));

  const addByName = () => {
    const n = newName.trim();
    if (!n) return;
    add(addPerson({ name: n, role: '', access: 'receives' }));
    setNewName('');
  };

  const initial = template?.participantIds ?? people.map((p) => p.id);
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
          <span className="note">{t('templates.selected', { n: selected.length, total: candidates.length })}</span>
        </legend>
        {candidates.map((p) => (
          <div key={p.id} className="tpl-person">
            <label className="tpl-person__main">
              <input type="checkbox" className="checkbox" checked={selected.includes(p.id)} onChange={() => toggle(p.id)} />
              <Avatar name={p.name} />
              <span className="t-strong">{p.name}</span>
              {p.id === account?.personId && <span className="tag tag--me">{t('common.me')}</span>}
              <span className="note truncate">{p.role}</span>
            </label>
            <button type="button" className="icon-btn" aria-label={t('templates.replace', { name: p.name })} title={t('templates.replace', { name: p.name })} onClick={() => setReplacing(p)}>
              <ArrowsLeftRightIcon size={20} aria-hidden />
            </button>
          </div>
        ))}
        <div className="tpl-person tpl-person--new">
          <span className="tpl-person__plus" aria-hidden>
            <PlusIcon size={16} weight="bold" />
          </span>
          <input
            className="tpl-person__input"
            placeholder={t('templates.newParticipantPh')}
            aria-label={t('templates.addPerson')}
            role="combobox"
            aria-expanded={q.length > 0}
            aria-controls="tpl-suggest"
            aria-autocomplete="list"
            aria-activedescendant={q ? `tpl-opt-${active}` : undefined}
            value={newName}
            onChange={(e) => (setNewName(e.target.value), setActive(0))}
            onKeyDown={(e) => {
              if (!q) return;
              if (e.key === 'ArrowDown') (e.preventDefault(), setActive((a) => Math.min(a + 1, matches.length)));
              else if (e.key === 'ArrowUp') (e.preventDefault(), setActive((a) => Math.max(a - 1, 0)));
              else if (e.key === 'Escape') (e.stopPropagation(), setNewName(''));
              else if (e.key === 'Enter') {
                e.preventDefault();
                if (matches[active]) pickExisting(matches[active].id);
                else addByName();
              }
            }}
          />
          {!q && (
            <button type="button" className="link-btn tpl-person__details" onClick={() => setCreating('add')}>
              {t('templates.withDetails')}
            </button>
          )}
        </div>
        {/* Predictive list: people already in Liminal first, "create new" last. Inline so the modal never clips it. */}
        {q && (
          <ul id="tpl-suggest" role="listbox" aria-label={t('templates.addPerson')} className="tpl-suggest">
            {matches.map((p, i) => (
              <li key={p.id} id={`tpl-opt-${i}`} role="option" aria-selected={i === active} className={`tpl-suggest__option${i === active ? ' is-active' : ''}`} onMouseEnter={() => setActive(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => pickExisting(p.id)}>
                <Avatar name={p.name} />
                <span className="who__text">
                  <span className="who__name truncate">{p.name}</span>
                  <span className="who__sub truncate">{[p.role, p.email].filter(Boolean).join(' · ')}</span>
                </span>
              </li>
            ))}
            <li id={`tpl-opt-${matches.length}`} role="option" aria-selected={active === matches.length} className={`tpl-suggest__option tpl-suggest__create${active === matches.length ? ' is-active' : ''}`} onMouseEnter={() => setActive(matches.length)} onMouseDown={(e) => e.preventDefault()} onClick={addByName}>
              <span className="tpl-person__plus" aria-hidden style={{ marginLeft: 0 }}>
                <PlusIcon size={16} weight="bold" />
              </span>
              <span className="who__name truncate">{t('templates.createNamed', { name: newName.trim() })}</span>
            </li>
          </ul>
        )}
      </fieldset>
      <Button variant="primary" disabled={!dirty} block onClick={save}>
        {template ? t('templates.saveChanges') : t('templates.save')}
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
      {editing && <EditTemplatePanel template={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
