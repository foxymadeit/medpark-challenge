import { ArrowsLeftRightIcon, CheckIcon, MicrophoneIcon, PlusIcon, UserPlusIcon, UsersThreeIcon } from '@phosphor-icons/react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AddPersonRow } from '../components/AddPersonRow';
import { Avatar } from '../components/Avatar';
import { Button } from '../components/Button';
import { Dialog } from '../components/Dialog';
import { PeopleStack } from '../components/PeopleStack';
import { MeetingTypeIcon } from '../components/MeetingTypeIcon';
import { PageHeader } from '../components/PageHeader';
import { Segmented } from '../components/Segmented';
import { TemplateBadge } from '../components/TemplateBadge';
import { TextField } from '../components/TextField';
import { useI18n } from '../i18n/I18nProvider';
import { COLOR_KEYS, PALETTE, templateColor, type ColorKey } from '../lib/colors';
import { suggestForType } from '../lib/participants';
import { AddParticipantModal } from './Participants';
import { useStore } from '../store/AppStore';
import { MEETING_TYPES, type MeetingType, type Person, type Template } from '../types';

/** Pick who takes a participant's place: click someone (the row stays highlighted), then Replace; or a new person. */
function ReplacePersonDialog({ person, options, onPick, onNew, onClose }: { person: Person; options: Person[]; onPick: (id: string) => void; onNew: () => void; onClose: () => void }) {
  const { t } = useI18n();
  const [chosen, setChosen] = useState<string>();
  return (
    <Dialog title={t('templates.replaceTitle', { name: person.name })} onClose={onClose} className="modal--replace">
      <p className="note">{options.length ? t('templates.replaceHint') : t('templates.noOthers')}</p>
      {options.length > 0 && (
        <ul className="replace-list" role="radiogroup" aria-label={t('templates.replaceTitle', { name: person.name })}>
          {options.map((p) => (
            <li key={p.id}>
              <button type="button" role="radio" aria-checked={chosen === p.id} className={`replace-list__item row-hover${chosen === p.id ? ' is-selected' : ''}`} onClick={() => setChosen(p.id)}>
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
      <div className="replace-actions">
        <Button icon={<UserPlusIcon size={20} aria-hidden />} onClick={onNew}>
          {t('templates.newPerson')}
        </Button>
        <Button variant="ink" disabled={!chosen} onClick={() => chosen && onPick(chosen)}>
          {t('templates.replaceConfirm')}
        </Button>
      </div>
    </Dialog>
  );
}

/** Template colour on the name's line: just the chosen colour; a click opens all of them. Esc / outside click closes. */
function ColorPicker({ value, onChange }: { value: ColorKey; onChange: (c: ColorKey) => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    wrap.current?.querySelector<HTMLElement>('[aria-checked=true]')?.focus();
    const onDown = (e: MouseEvent) => !wrap.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);
  const close = () => (setOpen(false), button.current?.focus());
  return (
    <span className="color-pick" ref={wrap} onKeyDown={(e) => open && e.key === 'Escape' && (e.stopPropagation(), close())}>
      <button
        ref={button}
        type="button"
        className="swatch color-pick__button"
        style={{ background: PALETTE[value].solid }}
        aria-label={`${t('templates.color')}: ${t(`colors.${value}`)}`}
        title={t(`colors.${value}`)}
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => (open ? close() : setOpen(true))}
      />
      {open && (
        <span className="swatches color-pick__panel" role="radiogroup" aria-label={t('templates.color')}>
          {COLOR_KEYS.map((c) => (
            <button
              key={c}
              type="button"
              role="radio"
              aria-checked={value === c}
              aria-label={t(`colors.${c}`)}
              title={t(`colors.${c}`)}
              className="swatch"
              style={{ background: PALETTE[c].solid, color: 'var(--sm-on-solid)' }}
              onClick={() => (onChange(c), close())}
            >
              {value === c && <CheckIcon size={16} weight="bold" aria-hidden />}
            </button>
          ))}
        </span>
      )}
    </span>
  );
}

/** T02 — template editor (New and Edit are this one window), a centred modal of a fixed size: only the people list scrolls. */
function EditTemplatePanel({ template, onClose }: { template?: Template; onClose: () => void }) {
  const { t } = useI18n();
  const { account, people, meetings, resolvePerson, saveTemplate, deleteTemplate, addPerson } = useStore();
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

  // Under the ticked people: suggestions for the meeting type, unticked, as many as fit in the list without scrolling
  // (rows are 48px; one row stays for "Add participant"). Ticking one moves it up; the next suggestion takes its place.
  const listRef = useRef<HTMLDivElement>(null);
  const [rowsFit, setRowsFit] = useState(0);
  useLayoutEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const measure = () => setRowsFit(Math.floor(el.clientHeight / 48));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const suggested = suggestForType(type, meetings, people, (id) => selected.includes(id), rowsFit - members.length - 1);

  // Unticking removes them from the template (and from this list).
  const remove = (id: string) => setSelected((s) => s.filter((x) => x !== id));
  const add = (id: string) => setSelected((s) => (s.includes(id) ? s : [...s, id]));
  // The newcomer takes the old participant's slot, so the template order is kept.
  const replace = (oldId: string, newId: string) =>
    setSelected((s) => (s.includes(newId) ? s.filter((x) => x !== oldId) : s.includes(oldId) ? s.map((x) => (x === oldId ? newId : x)) : [...s, newId]));

  const initial = template?.participantIds ?? (account ? [account.personId] : []);
  const dirty =
    name.trim() !== (template?.name ?? '') ||
    type !== (template?.type ?? 'medical') ||
    color !== (template ? templateColor(template) : 'blue') ||
    selected.length !== initial.length ||
    selected.some((id, i) => id !== initial[i]);

  // Save: a name is needed; editing, something must have changed too.
  const canSave = !!name.trim() && (!template || dirty);
  const save = () => {
    if (!name.trim()) return setError(t('common.required'));
    saveTemplate({ id: template?.id, name: name.trim(), type, color, participantIds: selected });
    onClose();
  };

  return (
    <Dialog title={template ? t('templates.panelTitle') : t('templates.new')} onClose={onClose} wide className="modal--template">
      <TextField editable label={t('templates.name')} placeholder={t(`templates.namePh.${type}`)} value={name} onChange={(e) => (setName(e.target.value), setError(undefined))} error={error} after={<ColorPicker value={color} onChange={setColor} />} />
      <div className="field">
        <span className="field__label">{t('templates.type')}</span>
        <Segmented<MeetingType> label={t('templates.type')} variant="fill" value={type} onChange={setType} options={MEETING_TYPES.map((m) => ({ value: m, label: t(`types.${m}`), icon: <MeetingTypeIcon type={m} /> }))} />
      </div>
      <fieldset className="tpl-people">
        <legend className="tpl-people__head">
          <span className="row" style={{ gap: 'var(--sm-space-2)' }}>
            <UsersThreeIcon size={20} aria-hidden />
            <span className="t-strong">{t('templates.participants')}</span>
          </span>
          <span className="note">{t('common.participantsCount', { count: members.length })}</span>
        </legend>
        <div className="tpl-people__list" ref={listRef}>
          {/* Who's in the template (untick to take them out), then suggestions for the type (tick to add). */}
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
          {suggested.map((p) => (
            <div key={p.id} className="tpl-person">
              <label className="tpl-person__main">
                <input type="checkbox" className="checkbox" checked={false} onChange={() => add(p.id)} aria-label={t('templates.addTo', { name: p.name })} />
                <Avatar name={p.name} />
                <span className="t-strong">{p.name}</span>
                <span className="note truncate">{p.role || p.email}</span>
              </label>
            </div>
          ))}
          {/* Add row: the + sits in the avatars' column; picked or created people join ticked. */}
          <AddPersonRow
            pool={others}
            known={[...people, ...members]}
            onPick={(p) => add(p.id)}
            onCreate={(typed) => add(addPerson({ ...typed, role: '', access: 'receives' }))}
          />
        </div>
      </fieldset>
      {/* Save across the form, like "Create participant"; Delete (editing only) under it. */}
      <div className="tpl-editor__actions">
        <Button variant="primary" block disabled={!canSave} onClick={save}>
          {template ? t('templates.saveChanges') : t('templates.save')}
        </Button>
        {template && (
          <Button variant="ghost" block className="btn--danger-text" onClick={() => setConfirmDelete(true)}>
            {t('templates.delete')}
          </Button>
        )}
      </div>

      {confirmDelete && template && (
        <Dialog title={t('templates.deleteTitle')} onClose={() => setConfirmDelete(false)}>
          <p className="lead">{t('templates.deleteLead')}</p>
          <div className="row" style={{ justifyContent: 'flex-end', gap: 'var(--sm-space-3)' }}>
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
      <PageHeader
        title={t('templates.title')}
        aside={
          <Button icon={<PlusIcon size={20} aria-hidden />} onClick={() => setEditing('new')}>
            {t('templates.new')}
          </Button>
        }
      />
      <ul className="tpl-grid">
        {templates.map((tpl) => (
          <li key={tpl.id} className="card card--pad tpl-card">
            <div className="tpl-card__head">
              <TemplateBadge color={templateColor(tpl)} type={tpl.type} />
              <div className="stack" style={{ gap: 'var(--sm-space-1)', minWidth: 0 }}>
                <h2 className="t-h3">{tpl.name}</h2>
                <p className="note">{t('templates.meta', { type: t(`types.${tpl.type}`), count: tpl.participantIds.length })}</p>
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
