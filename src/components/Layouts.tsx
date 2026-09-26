import { CaretDownIcon, ClockCounterClockwiseIcon, GearSixIcon, ListChecksIcon, ListIcon, XIcon, MicrophoneIcon, SignOutIcon, UsersThreeIcon } from '@phosphor-icons/react';
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { LANGS, useI18n, type Lang } from '../i18n/I18nProvider';
import { useStore } from '../store/AppStore';
import { Avatar } from './Avatar';
import { Logo } from './Logo';
import { Segmented } from './Segmented';

function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <Segmented<Lang>
      label={t('common.language')}
      variant="lang"
      value={lang}
      onChange={setLang}
      options={LANGS.map((l) => ({ value: l, label: t(`lang.${l}`) }))}
    />
  );
}

/** Avatar + name → menu with the user's details, Settings and Log out. */
function AccountMenu() {
  const { t } = useI18n();
  const { account, logOut } = useStore();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    wrap.current?.querySelector<HTMLElement>('[role=menuitem]')?.focus();
    const onDown = (e: MouseEvent) => !wrap.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  if (!account) return null;

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      setOpen(false);
      button.current?.focus();
      return;
    }
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    const items = Array.from(wrap.current?.querySelectorAll<HTMLElement>('[role=menuitem]') ?? []);
    const i = items.indexOf(document.activeElement as HTMLElement);
    items[(i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus();
    e.preventDefault();
  };

  const go = (fn: () => void) => () => {
    setOpen(false);
    fn();
  };

  return (
    <div className="account" ref={wrap} onKeyDown={onKey}>
      <button ref={button} type="button" className="account__button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Avatar name={account.name} strong />
        <span className="t-button">{account.name}</span>
        <CaretDownIcon size={16} aria-hidden />
      </button>
      {open && (
        <div className="account__menu" role="menu" aria-label={t('account.menu')}>
          <div className="account__who">
            <span className="who__name">{account.name}</span>
            <span className="who__sub">{account.email}</span>
            {account.role && <span className="who__sub">{account.role}</span>}
          </div>
          <button type="button" role="menuitem" className="dropdown__option account__item" onClick={go(() => navigate('/settings'))}>
            <span className="row">
              <GearSixIcon size={20} aria-hidden />
              {t('account.settings')}
            </span>
          </button>
          <button
            type="button"
            role="menuitem"
            className="dropdown__option account__item"
            onClick={go(() => {
              logOut();
              navigate('/login');
            })}
          >
            <span className="row">
              <SignOutIcon size={20} aria-hidden />
              {t('account.logOut')}
            </span>
          </button>
        </div>
      )}
    </div>
  );
}

function TopBar({ showAccount, menuOpen, onMenu }: { showAccount: boolean; menuOpen?: boolean; onMenu?: () => void }) {
  const { t } = useI18n();
  const { account, signedIn } = useStore();
  return (
    <header className="topbar">
      <a href="#main" className="skip-link">
        {t('common.skipToContent')}
      </a>
      {onMenu && (
        // Only visible ≤1024px, where the sidebar becomes a drawer.
        <button type="button" className="icon-btn icon-btn--lg topbar__menu" aria-label={t('common.menu')} aria-expanded={menuOpen} aria-controls="sidenav" onClick={onMenu}>
          {menuOpen ? <XIcon size={20} aria-hidden /> : <ListIcon size={20} aria-hidden />}
        </button>
      )}
      <Link to={signedIn ? '/new' : '/'} className="brand">
        <Logo />
        <span className="brand__name">{t('common.appName')}</span>
      </Link>
      <div className="topbar__right">
        <LanguageSwitch />
        {showAccount && account && <AccountMenu />}
      </div>
    </header>
  );
}

// Sidebar order follows the real screens (New meeting · History · Participants · Templates).
const NAV = [
  { to: '/new', key: 'nav.newMeeting', Icon: MicrophoneIcon, match: ['/new', '/recording', '/upload', '/processing', '/review', '/sent'] },
  { to: '/participants', key: 'nav.participants', Icon: UsersThreeIcon, match: ['/participants'] },
  { to: '/templates', key: 'nav.templates', Icon: ListChecksIcon, match: ['/templates'] },
  { to: '/history', key: 'nav.history', Icon: ClockCounterClockwiseIcon, match: ['/history'] },
];

function SideNav({ open }: { open: boolean }) {
  const { t } = useI18n();
  const { pathname } = useLocation();
  return (
    <nav id="sidenav" className={`sidenav${open ? ' is-open' : ''}`} aria-label={t('common.mainNav')}>
      {NAV.map(({ to, key, Icon, match }) => {
        const active = match.some((m) => pathname === m || pathname.startsWith(`${m}/`));
        return (
          <NavLink key={to} to={to} className={`nav-item${active ? ' is-active' : ''}`} aria-current={active ? 'page' : undefined}>
            <Icon size={20} aria-hidden />
            {t(key)}
          </NavLink>
        );
      })}
    </nav>
  );
}

/** Sign up / Log in: top bar without account, no sidebar. */
export function AccessLayout() {
  return (
    <div className="app">
      <TopBar showAccount={false} />
      <main id="main" className="main main--center">
        <Outlet />
      </main>
    </div>
  );
}

/** Onboarding: top bar with account, no sidebar. */
export function OnboardingLayout() {
  return (
    <div className="app">
      <TopBar showAccount />
      <main id="main" className="main">
        <Outlet />
      </main>
    </div>
  );
}

/** App shell (Figma "_Shell"): top bar + 240px sidebar + content. */
export function AppLayout() {
  // Drawer state for tablet/phone; on desktop the sidebar is always shown and this is ignored.
  const [navOpen, setNavOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setNavOpen(false), [pathname]);
  useEffect(() => {
    if (!navOpen) return;
    document.querySelector<HTMLElement>('#sidenav .nav-item')?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && setNavOpen(false);
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [navOpen]);

  return (
    <div className="app">
      <TopBar showAccount menuOpen={navOpen} onMenu={() => setNavOpen((o) => !o)} />
      <div className="app__body">
        <SideNav open={navOpen} />
        {navOpen && <div className="nav-scrim" aria-hidden onClick={() => setNavOpen(false)} />}
        <main id="main" className="main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

/** Route guard: no account → sign up; signed out → log in; not onboarded → onboarding. */
export function RequireAuth({ children, onboarding }: { children: ReactNode; onboarding?: boolean }) {
  const { account, signedIn, onboarded } = useStore();
  if (!account) return <Navigate to="/signup" replace />;
  if (!signedIn) return <Navigate to="/login" replace />;
  if (!onboarding && !onboarded) return <Navigate to="/onboarding/1" replace />;
  return <>{children}</>;
}
