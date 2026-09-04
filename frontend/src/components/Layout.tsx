import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { BarChart3, Ban, ChevronLeft, ChevronRight, ClipboardList, LogOut, Menu, MessageSquare, PackageSearch, Settings as SettingsIcon, X } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, getInitials } from '@/lib/utils';

const items = [
  { label: 'Дашборд', to: '/', icon: BarChart3, enabled: true },
  { label: 'Мои заявки', to: '/requests', icon: ClipboardList, enabled: true },
  { label: 'Переписка', to: '/messages', icon: MessageSquare, enabled: true },
  { label: 'Поставщики', to: '/suppliers', icon: PackageSearch, enabled: true },
  { label: 'Чёрный список', to: '/blacklist', icon: Ban, enabled: true },
  { label: 'Настройки', to: '/settings', icon: SettingsIcon, enabled: true },
];

const SIDEBAR_COLLAPSED_STORAGE_KEY = 'supplydesk.sidebar.collapsed';

function isSafeTestRuntime(): boolean {
  return window.location.hostname === '127.0.0.1' && window.location.port === '18000';
}

function readSidebarCollapsed(): boolean {
  try {
    const stored = window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY);
    return stored === null ? true : stored === 'true';
  } catch {
    return true;
  }
}

/** Графитовая навигационная панель — единый язык для всего приложения
 *  (Documents/28-8/DESIGN.md: «graphite navigation rail»), не только для дашборда.
 *
 *  До этой правки цвет панели переключался по `location.pathname === '/'`:
 *  тёмная на дашборде, белая на всех остальных экранах. Находка независимого
 *  аудита (Documents/28-8/messages-and-mail-audit.md): «дашборд и остальные экраны
 *  используют разные варианты навигационной темы» — не отдельное продуктовое
 *  решение, а незавершённый переезд. Панель теперь одна и та же на каждом
 *  маршруте, а рабочая область (`<main>`) остаётся светлой, как и предписано. */
export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readSidebarCollapsed);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileCloseButtonRef = useRef<HTMLButtonElement>(null);
  const mobileSidebarRef = useRef<HTMLElement>(null);
  const wasMobileOpen = useRef(false);
  // Счётчик писем без привязки к заявке. Такое письмо — это ответ, который
  // система не смогла отнести к закупке; без пометки в навигации оно тихо
  // лежало во вкладке «Без привязки», и его легко было не заметить.
  const [unmatchedMail, setUnmatchedMail] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.dashboardSummary()
      .then((data) => { if (!cancelled) setUnmatchedMail(data.kpis.unmatched_mail ?? 0); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [location.pathname]);

  useEffect(() => {
    const handleUnmatchedCountChange = (event: Event) => {
      const delta = Number((event as CustomEvent<{ delta?: number }>).detail?.delta ?? 0);
      if (Number.isFinite(delta) && delta !== 0) setUnmatchedMail((value) => Math.max(0, value + delta));
    };
    window.addEventListener('supplydesk:unmatched-mail-changed', handleUnmatchedCountChange);
    return () => window.removeEventListener('supplydesk:unmatched-mail-changed', handleUnmatchedCountChange);
  }, []);

  // Durable enrichment jobs are deliberately separate from a request search:
  // a request can finish while Checko is rate-limited. Any authenticated page
  // advances at most one due stage, so this also works in a serverless process
  // without relying on a daemon thread that Vercel may freeze.
  useEffect(() => {
    let cancelled = false;
    let busy = false;
    const tick = async () => {
      if (cancelled || busy) return;
      busy = true;
      try {
        await api.stepEnrichment();
      } catch {
        // The job keeps its lease/state in the database; a later tick retries.
      } finally {
        busy = false;
      }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const sidebar = mobileSidebarRef.current;
    if (sidebar) sidebar.toggleAttribute('inert', !mobileOpen);
  }, [mobileOpen]);

  useEffect(() => {
    if (!mobileOpen) {
      if (wasMobileOpen.current) mobileMenuButtonRef.current?.focus();
      wasMobileOpen.current = false;
      return;
    }
    wasMobileOpen.current = true;
    mobileCloseButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mobileOpen]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(sidebarCollapsed));
    } catch {
      // A restricted storage context should not make navigation unusable.
    }
  }, [sidebarCollapsed]);

  const sidebarContent = (compact: boolean, showCollapse = true) => (
    <>
      <div className={cn('flex h-[76px] items-center border-b border-ink-800', compact ? 'relative flex-col justify-end gap-1 px-2 pb-2 pt-8' : 'px-4')}>
        <button
          type="button"
          onClick={() => showCollapse ? setSidebarCollapsed((value) => !value) : navigate('/')}
          aria-label={showCollapse ? (compact ? 'Развернуть меню' : 'Свернуть меню') : 'Открыть дашборд'}
          aria-expanded={showCollapse ? !compact : undefined}
          aria-controls={showCollapse ? 'desktop-sidebar' : undefined}
          title={showCollapse ? (compact ? 'Развернуть меню' : 'Свернуть меню') : undefined}
          className={cn('flex h-12 min-w-0 items-center rounded-xl text-left transition-colors hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500', compact ? 'w-12 justify-center' : 'flex-1 px-3')}
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent-600 text-white shadow-soft">
            {showCollapse ? (compact ? <ChevronRight size={18} strokeWidth={2.5} aria-hidden="true" /> : <ChevronLeft size={18} strokeWidth={2.5} aria-hidden="true" />) : '›'}
          </span>
          <span className={cn('ml-3 min-w-0', compact && 'sr-only')}>
            <span className="block text-base font-bold tracking-tight text-white">SupplyDesk</span>
            <span className="block text-2xs font-medium uppercase tracking-[0.16em] text-ink-400">Procurement OS</span>
          </span>
        </button>
      </div>
      <nav aria-label="Основная навигация" className={cn('flex-1 space-y-1 py-7', compact ? 'px-2' : 'px-4')}>
        <div className={cn('mb-3 px-3 text-2xs font-bold uppercase tracking-[0.16em] text-ink-400', compact && 'sr-only')}>Рабочее пространство</div>
        {items.map(({ label, to, icon: Icon, enabled }) =>
          enabled ? (
            <NavLink
              key={label}
              to={to}
              end={to === '/'}
              aria-label={label}
              title={compact ? label : undefined}
              className={({ isActive }) => cn(
                'group relative flex items-center rounded-xl py-3 text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2',
                compact ? 'justify-center px-2' : 'gap-3 px-3',
                isActive
                  ? compact ? 'bg-white/10 text-white ring-1 ring-inset ring-accent-400/60' : 'bg-white/10 text-white'
                  : 'text-ink-300 hover:bg-white/5 hover:text-white',
              )}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span className={cn('flex-1', compact && 'sr-only')}>{label}</span>
              {to === '/messages' && unmatchedMail > 0 && (
                <span
                  title={`${unmatchedMail} писем без привязки к заявке`}
                  aria-label={`${unmatchedMail} писем без привязки к заявке`}
                  className={cn('rounded-full bg-amber-500 px-1.5 py-px text-2xs font-bold text-white', compact ? 'absolute right-1 top-1' : 'shrink-0')}
                >
                  {unmatchedMail}
                </span>
              )}
            </NavLink>
          ) : (
            <div key={label} aria-label={label} title={compact ? label : undefined} className={cn('flex cursor-not-allowed items-center rounded-xl py-3 text-sm font-semibold text-ink-300', compact ? 'justify-center px-2' : 'gap-3 px-3')}>
              <Icon size={18} strokeWidth={1.8} />
              <span className={cn(compact && 'sr-only')}>{label}</span>
              <span className={cn('ml-auto text-2xs font-bold uppercase tracking-wider', compact && 'sr-only')}>скоро</span>
            </div>
          )
        )}
      </nav>
      <div className="border-t border-ink-800 p-4">
        <div className={cn('flex items-center rounded-xl py-3', compact ? 'flex-col gap-2 px-0' : 'gap-3 px-3')}>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-100 text-xs font-bold text-accent-700">
            {getInitials(user?.display_name || user?.email || '?')}
          </div>
          <div className={cn('min-w-0 flex-1', compact && 'sr-only')}>
            <div className="truncate text-xs font-bold text-white">{user?.display_name || user?.email}</div>
            <div className="truncate text-xs text-ink-400">{user?.workspace_name}</div>
          </div>
          <button
            onClick={handleLogout}
            title="Выйти"
            aria-label="Выйти"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-400 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </>
  );

  return (
    <div data-app-shell className="min-h-screen bg-ink-50 text-ink-900">
      {isSafeTestRuntime() && (
        <div
          role="status"
          data-runtime-badge
          className="sticky top-0 z-40 flex min-h-8 items-center justify-center border-b border-amber-300 bg-amber-100 px-4 py-2 text-center text-[11px] font-extrabold uppercase tracking-[0.12em] text-amber-950"
        >
          SAFE TEST <span aria-hidden="true">·</span> DISPOSABLE DATA <span aria-hidden="true">·</span> PORT 18000
        </div>
      )}
      <a href="#main-content" className="fixed left-4 top-4 z-[80] -translate-y-20 rounded-lg bg-white px-3 py-2 text-xs font-bold text-ink-900 shadow-float transition-transform focus:translate-y-0 focus:outline-none focus:ring-2 focus:ring-accent-500">
        Перейти к содержимому
      </a>
      {/* Mobile top bar — the only way to reach navigation below the lg breakpoint,
          since the real sidebar is hidden there (see S-01 in the defect ledger). */}
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-ink-800 bg-ink-900 px-4 text-white lg:hidden">
        <button
          ref={mobileMenuButtonRef}
          onClick={() => setMobileOpen(true)}
          aria-label="Открыть меню"
          aria-expanded={mobileOpen}
          aria-controls="mobile-sidebar"
          className="flex h-10 w-10 items-center justify-center rounded-lg text-ink-300 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
        >
          <Menu size={20} />
        </button>
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-600 text-sm font-bold text-white">›</span>
        <span className="text-sm font-bold tracking-tight">SupplyDesk</span>
      </header>

      {mobileOpen && (
        <div aria-hidden="true" className="fixed inset-0 z-40 bg-ink-900/30 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}
      <aside
        id="desktop-sidebar"
        aria-label="Основная навигация"
        className={cn('fixed inset-y-0 left-0 z-20 hidden flex-col border-r border-ink-800 bg-ink-900 transition-[width] duration-200 ease-out lg:flex', sidebarCollapsed ? 'w-[76px]' : 'w-[248px]')}
      >
        {sidebarContent(sidebarCollapsed)}
      </aside>
      <aside
        id="mobile-sidebar"
        ref={mobileSidebarRef}
        aria-label="Мобильная навигация"
        aria-hidden={!mobileOpen}
        className={`fixed inset-y-0 left-0 z-50 flex w-[248px] flex-col border-r border-ink-800 bg-ink-900 transition-transform duration-200 lg:hidden ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <button
          ref={mobileCloseButtonRef}
          onClick={() => setMobileOpen(false)}
          aria-label="Закрыть меню"
          className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-lg text-ink-400 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 lg:hidden"
        >
          <X size={18} />
        </button>
        {sidebarContent(false, false)}
      </aside>
      <main id="main-content" tabIndex={-1} className={cn('min-w-0 lg:transition-[padding-left] lg:duration-200 lg:ease-out', sidebarCollapsed ? 'lg:pl-[76px]' : 'lg:pl-[248px]')}>
        <Outlet />
      </main>
    </div>
  );
}
