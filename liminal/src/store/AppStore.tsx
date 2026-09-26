import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { cardioTasks, cardioTranscript, demoAccounts, demoDirectory, demoPeople, materialiseTasks, seedMeetings, seedTemplates, YOU_ID } from '../mocks';
import { todayISO, uid } from '../lib/format';
import { retokenize, tokenize } from '../lib/transcript';
import type { Preferences, Account, Meeting, MeetingSource, MeetingType, ParticipantSnapshot, Person, Task, Template, SpokenLang } from '../types';

/**
 * Frontend-only mock store. Everything persists to localStorage so the demo
 * survives reloads. Append `?reset` to any URL to start over.
 */

export interface Draft {
  type: MeetingType;
  templateId?: string;
  /** Name typed on New meeting; wins over the template name. */
  title?: string;
  /** Meeting date chosen on New meeting (ISO); defaults to today. */
  date?: string;
  emails: string[];
}

interface State {
  account: Account | null;
  signedIn: boolean;
  onboarded: boolean;
  people: Person[];
  meetings: Meeting[];
  templates: Template[];
  draft: Draft;
  /** True when the data came from a demo login (demo accounts stay offered on Log in). */
  demo?: boolean;
}

export type LogInResult = 'ok' | 'receives-only' | 'no-account';

const STORAGE_KEY = 'liminal:state:v1';

const initialState = (): State => ({
  account: null,
  signedIn: false,
  onboarded: false,
  people: [],
  meetings: seedMeetings,
  templates: seedTemplates,
  draft: { type: 'medical', emails: [] },
});

function load(): State {
  try {
    if (new URLSearchParams(location.search).has('reset')) {
      localStorage.removeItem(STORAGE_KEY);
      history.replaceState(null, '', location.pathname);
    }
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...initialState(), ...JSON.parse(raw) };
  } catch {
    /* ignore corrupt or blocked storage */
  }
  return initialState();
}

function useStoreValue() {
  const [state, setState] = useState<State>(load);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      /* storage unavailable — keep in memory */
    }
  }, [state]);

  /** Directory first, then mocked colleagues referenced by templates/history. */
  const resolvePerson = useCallback(
    (id: string): Person | undefined => state.people.find((p) => p.id === id) ?? demoPeople.find((p) => p.id === id),
    [state.people],
  );

  const signUp = useCallback((name: string, email: string) => {
    const you: Person = { id: YOU_ID, name, email, role: '', access: 'admin' };
    setState((s) => ({
      ...s,
      account: { personId: YOU_ID, name, email, role: '', department: '', meetingTypes: [] },
      signedIn: true,
      onboarded: false,
      people: [you], // first user = Admin
    }));
  }, []);

  const updateAccount = useCallback((patch: Partial<Account>) => {
    setState((s) => {
      if (!s.account) return s;
      const account = { ...s.account, ...patch };
      const people = s.people.map((p) => (p.id === account.personId ? { ...p, name: account.name, role: account.role, email: account.email } : p));
      const draft = patch.meetingTypes?.length ? { ...s.draft, type: patch.meetingTypes[0] } : s.draft;
      return { ...s, account, people, draft };
    });
  }, []);

  const preferences: Preferences = { reviewMode: 'manual', ...state.account?.preferences };

  const updatePreferences = useCallback((patch: Partial<Preferences>) => {
    setState((s) => (s.account ? { ...s, account: { ...s.account, preferences: { reviewMode: 'manual', ...s.account.preferences, ...patch } } } : s));
  }, []);

  const logOut = useCallback(() => setState((s) => ({ ...s, signedIn: false })), []);

  const finishOnboarding = useCallback(() => setState((s) => ({ ...s, onboarded: true })), []);

  /** Returns the person's id (an existing one when the email matches a known colleague). */
  const addPerson = useCallback((p: Omit<Person, 'id'> & { id?: string }) => {
    // Same email as a known colleague → same person (keeps template/history links intact).
    const known = p.email ? demoPeople.find((d) => d.email?.toLowerCase() === p.email!.toLowerCase()) : undefined;
    const id = p.id ?? known?.id ?? uid('p');
    setState((s) => (s.people.some((x) => x.id === id) ? s : { ...s, people: [...s.people, { ...p, id }] }));
    return id;
  }, []);

  const updatePerson = useCallback((id: string, patch: Partial<Person>) => {
    setState((s) => ({ ...s, people: s.people.map((p) => (p.id === id ? { ...p, ...patch } : p)) }));
  }, []);

  const removePerson = useCallback((id: string) => {
    // Also drop them from templates; sent meetings keep their frozen participant snapshot.
    setState((s) => ({
      ...s,
      people: s.people.filter((p) => p.id !== id),
      templates: s.templates.map((tpl) => (tpl.participantIds.includes(id) ? { ...tpl, participantIds: tpl.participantIds.filter((x) => x !== id) } : tpl)),
    }));
  }, []);

  const setDraft = useCallback((patch: Partial<Draft>) => setState((s) => ({ ...s, draft: { ...s.draft, ...patch } })), []);

  const updateMeeting = useCallback((id: string, patch: Partial<Meeting>) => {
    setState((s) => ({ ...s, meetings: s.meetings.map((m) => (m.id === id ? { ...m, ...patch } : m)) }));
  }, []);

  /** Snapshot a person's current details for a meeting. */
  const snapshot = useCallback(
    (id: string): ParticipantSnapshot | null => {
      const p = resolvePerson(id);
      return p ? { personId: p.id, name: p.name, email: p.email, roleThen: p.role } : null;
    },
    [resolvePerson],
  );

  /** Create a meeting from the current draft (called on Stop / Write minutes). */
  const createMeetingFromDraft = useCallback(
    (source: MeetingSource, durationMin: number, fileName?: string, fallbackTitle = ''): string => {
      const id = uid('m');
      const { draft, templates, people } = state;
      const template = templates.find((t) => t.id === draft.templateId);
      const ids = template ? template.participantIds : [state.account?.personId ?? YOU_ID];
      const participants = ids.map(snapshot).filter((x): x is ParticipantSnapshot => !!x);
      // Optional emails typed on New meeting become "Receives MoM" guests of this meeting.
      for (const email of draft.emails) {
        const known = people.find((p) => p.email?.toLowerCase() === email.toLowerCase());
        if (known && !participants.some((x) => x.personId === known.id)) participants.push(snapshot(known.id)!);
        if (!known) participants.push({ personId: uid('guest'), name: email, email, roleThen: '' });
      }
      // Meetings can't be dated ahead (the picker also blocks it); an older saved future date falls back to today.
      const date = draft.date && draft.date < todayISO() ? draft.date : todayISO();
      const title = draft.title?.trim() || template?.name || fileName || fallbackTitle;
      const meeting: Meeting = {
        id,
        title,
        type: draft.type,
        date,
        durationMin: Math.max(1, durationMin),
        source,
        fileName,
        status: 'processing',
        participants,
        // MOCK: the AI output is the example Cardiology board minutes.
        transcript: cardioTranscript,
        tasks: materialiseTasks(date, id, cardioTasks),
      };
      // Name, date and added people belong to this meeting only; the next one starts fresh (type and template stay).
      setState((s) => ({ ...s, meetings: [meeting, ...s.meetings], draft: { ...s.draft, title: undefined, date: undefined, emails: [] } }));
      return id;
    },
    [state, snapshot],
  );

  /** Replace one transcript token (word / term). A corrected term that names a patient also renames it in tasks. */
  const correctToken = useCallback((meetingId: string, lineIdx: number, tokenIdx: number, value: string) => {
    setState((s) => ({
      ...s,
      meetings: s.meetings.map((m) => {
        if (m.id !== meetingId) return m;
        const transcript = m.transcript.map((line, i) => {
          if (i !== lineIdx) return line;
          const tokens = (line.tokens ?? tokenize(line.text)).map((tok, j) => (j === tokenIdx ? { ...tok, text: value, fixed: true } : tok));
          return { ...line, tokens };
        });
        const old = (m.transcript[lineIdx].tokens ?? tokenize(m.transcript[lineIdx].text))[tokenIdx];
        const tasks = old?.kind === 'kw' ? m.tasks.map((t) => (t.patient.toLowerCase() === old.text.toLowerCase() ? { ...t, patient: value } : t)) : m.tasks;
        return { ...m, transcript, tasks };
      }),
    }));
  }, []);

  /** Flag (or clear) the language of one word — kept on the token as a training label. */
  const flagTokenLang = useCallback((meetingId: string, lineIdx: number, tokenIdx: number, lang: SpokenLang | undefined) => {
    setState((s) => ({
      ...s,
      meetings: s.meetings.map((m) =>
        m.id !== meetingId
          ? m
          : { ...m, transcript: m.transcript.map((line, i) => (i !== lineIdx ? line : { ...line, tokens: (line.tokens ?? tokenize(line.text)).map((tok, j) => (j === tokenIdx ? { ...tok, lang } : tok)) })) },
      ),
    }));
  }, []);

  /** Delete one word/term from the transcript, with the space next to it so no double spaces remain. */
  const removeToken = useCallback((meetingId: string, lineIdx: number, tokenIdx: number) => {
    setState((s) => ({
      ...s,
      meetings: s.meetings.map((m) => {
        if (m.id !== meetingId) return m;
        const transcript = m.transcript.map((line, i) => {
          if (i !== lineIdx) return line;
          const tokens = [...(line.tokens ?? tokenize(line.text))];
          const before = tokens[tokenIdx - 1]?.kind === 'space';
          const after = tokens[tokenIdx + 1]?.kind === 'space';
          // Prefer dropping the space before; at the start of a line drop the one after.
          tokens.splice(before ? tokenIdx - 1 : tokenIdx, before || after ? 2 : 1);
          // Removing the first word must not leave orphan punctuation (": I will…").
          while (tokens[0] && (tokens[0].kind === 'punct' || tokens[0].kind === 'space')) tokens.shift();
          return { ...line, tokens };
        });
        return { ...m, transcript };
      }),
    }));
  }, []);

  /** Replace a whole sentence (keeps its highlighted terms where they still appear). */
  const editLine = useCallback((meetingId: string, lineIdx: number, text: string) => {
    setState((s) => ({
      ...s,
      meetings: s.meetings.map((m) =>
        m.id !== meetingId ? m : { ...m, transcript: m.transcript.map((line, i) => (i !== lineIdx ? line : { ...line, tokens: retokenize(text, line.tokens ?? tokenize(line.text)), edited: true })) },
      ),
    }));
  }, []);

  /** Drop a whole sentence from the transcript (tasks are left as they are). */
  const removeLine = useCallback((meetingId: string, lineIdx: number) => {
    setState((s) => ({ ...s, meetings: s.meetings.map((m) => (m.id !== meetingId ? m : { ...m, transcript: m.transcript.filter((_, i) => i !== lineIdx) })) }));
  }, []);

  const setTasks = useCallback((meetingId: string, tasks: Task[]) => updateMeeting(meetingId, { tasks }), [updateMeeting]);

  /** Send: freeze roles as they are today and mark sent. */
  const sendMeeting = useCallback(
    (id: string) => {
      setState((s) => ({
        ...s,
        meetings: s.meetings.map((m) => {
          if (m.id !== id) return m;
          const participants = m.participants.map((p) => {
            const now = s.people.find((x) => x.id === p.personId) ?? demoPeople.find((x) => x.id === p.personId);
            return now ? { ...p, name: now.name, email: now.email, roleThen: now.role } : p;
          });
          return { ...m, participants, status: 'sent', sentTo: participants.filter((p) => p.email).length };
        }),
      }));
    },
    [],
  );

  const saveTemplate = useCallback((t: Omit<Template, 'id'> & { id?: string }) => {
    setState((s) => {
      if (t.id && s.templates.some((x) => x.id === t.id)) {
        return { ...s, templates: s.templates.map((x) => (x.id === t.id ? { ...x, ...t, id: x.id } : x)) };
      }
      return { ...s, templates: [...s.templates, { ...t, id: uid('t') }] };
    });
  }, []);

  /**
   * MOCK auth — any password works.
   *  1. Someone in this browser's Participants with Organizer/Admin access → logged in as them.
   *  2. "Receives MoM only" → no login needed (they get the minutes by email).
   *  3. Fresh browser (or demo data) + a demo account email → loads the demo dataset.
   */
  const logIn = useCallback(
    (email: string): LogInResult => {
      const e = email.trim().toLowerCase();
      const asUser = (s: State, p: Person): State => ({
        ...s,
        signedIn: true,
        account: {
          personId: p.id,
          name: p.name,
          email: p.email ?? e,
          role: p.role,
          department: s.account?.personId === p.id ? s.account.department : '',
          meetingTypes: s.account?.meetingTypes.length ? s.account.meetingTypes : ['medical'],
          preferences: s.account?.preferences,
        },
      });

      const person = state.people.find((p) => p.email?.toLowerCase() === e);
      if (person) {
        if (person.access === 'receives') return 'receives-only';
        setState((s) => asUser(s, person));
        return 'ok';
      }
      const demo = demoAccounts.find((a) => a.email.toLowerCase() === e);
      if (demo && (!state.account || state.demo)) {
        const people = demoDirectory();
        const p = people.find((x) => x.id === demo.personId)!;
        setState((s) =>
          asUser(
            { ...initialState(), people, onboarded: true, demo: true, account: { personId: p.id, name: p.name, email: p.email!, role: p.role, department: 'Cardiology', meetingTypes: ['medical', 'executive'] }, draft: s.draft },
            p,
          ),
        );
        return 'ok';
      }
      return 'no-account';
    },
    [state.people, state.account, state.demo],
  );

  return {
    ...state,
    resolvePerson,
    preferences,
    updatePreferences,
    logOut,
    signUp,
    logIn,
    updateAccount,
    finishOnboarding,
    addPerson,
    updatePerson,
    removePerson,
    setDraft,
    createMeetingFromDraft,
    updateMeeting,
    setTasks,
    correctToken,
    removeToken,
    flagTokenLang,
    editLine,
    removeLine,
    sendMeeting,
    saveTemplate,
  };
}

export type AppStore = ReturnType<typeof useStoreValue>;
const StoreContext = createContext<AppStore | null>(null);

export function AppStoreProvider({ children }: { children: ReactNode }) {
  const value = useStoreValue();
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error('useStore must be used inside <AppStoreProvider>');
  return ctx;
}

