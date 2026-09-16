import clsx from 'clsx';
import {
  Ban,
  Inbox,
  LayoutGrid,
  ListChecks,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Truck,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/AuthContext';
import { useApiData } from '../../lib/useApiData';
import { useIsNarrowViewport } from '../../lib/useIsNarrowViewport';
import { Avatar } from '../ui/Avatar';
import { SupportChat } from '../SupportChat';

const nav = [
  { to: '/', label: 'Дашборд', icon: LayoutGrid, end: true },
  { to: '/requests', label: 'Заявки', icon: ListChecks },
  { to: '/suppliers', label: 'Поставщики', icon: Truck },
  { to: '/messages', label: 'Сообщения', icon: Inbox },
  { to: '/blacklist', label: 'Чёрный список', icon: Ban },
  { to: '/settings', label: 'Настройки', icon: Settings },
];

const COLLAPSED_STORAGE_KEY = 'supplydesk.sidebar.collapsed';

function savedCollapsedPreference(): boolean | null {
  try {
    const value = window.localStorage.getItem(COLLAPSED_STORAGE_KEY);
    return value === 'true' ? true : value === 'false' ? false : null;
  } catch {
    // Storage can be unavailable in a private or restricted browser context.
    return null;
  }
}

function useNavCounts() {
  const dashboard = useApiData(() => api.dashboardSummary(), []);
  const threads = useApiData(() => api.listThreads().then((r) => r.items), []);
  const attention = dashboard.status === 'ready' ? dashboard.data.kpis.attention : 0;
  const unread = threads.status === 'ready' ? threads.data.reduce((sum, t) => sum + t.unread_count, 0) : 0;
  return { attention, unread };
}

export function Sidebar() {
  const isNarrow = useIsNarrowViewport();
  const storedPreference = savedCollapsedPreference();
  const [collapsed, setCollapsed] = useState(() => storedPreference ?? isNarrow);
  // A desktop preference must not make the working area unusable on a phone.
  // Keep the preference intact for the next wide viewport, but always render
  // the navigation as its icon rail below the shared mobile breakpoint.
  const compact = isNarrow || collapsed;
  // Only auto-follow the viewport before the user has touched the toggle
  // themselves -- once they expand on a narrow screen (or collapse on a
  // wide one), that manual choice sticks instead of being overridden on
  // every resize/rotation.
  const [userOverride, setUserOverride] = useState(() => storedPreference !== null);
  useEffect(() => {
    if (!userOverride) setCollapsed(isNarrow);
  }, [isNarrow, userOverride]);
  const { user } = useAuth();
  const { attention, unread } = useNavCounts();
  const badgeFor: Record<string, number> = { '/requests': attention, '/messages': unread };
  // The current auth API deliberately exposes one display-name string, not
  // separate first/last-name fields. Keep it verbatim rather than guessing
  // which word is a surname; missing values use an explicit, non-fictional
  // fallback.
  const profileName = user?.display_name?.trim() || 'Пользователь';
  const workspaceName = user?.workspace_name?.trim() || 'Организация не указана';

  return (
    <aside
      className={clsx(
        'flex h-full shrink-0 flex-col bg-rail transition-[width] duration-150',
        compact ? 'w-[64px]' : 'w-[224px]',
      )}
    >
      <div className={clsx('flex h-14 items-center border-b border-rail-border', compact ? 'justify-center px-0' : 'justify-between px-4')}>
        {!compact && (
          <span className="font-display text-[15px] font-semibold tracking-tight text-rail-text-active">
            SupplyDesk
          </span>
        )}
        <button
          type="button"
          onClick={() => {
            setUserOverride(true);
            setCollapsed((current) => {
              const next = !current;
              try {
                window.localStorage.setItem(COLLAPSED_STORAGE_KEY, String(next));
              } catch {
                // The current interaction still works when storage is blocked.
              }
              return next;
            });
          }}
          className={clsx(
            'flex h-7 w-7 items-center justify-center rounded-md text-rail-text-dim hover:bg-rail-hover hover:text-rail-text-active',
            isNarrow && 'pointer-events-none invisible',
          )}
          aria-label={compact ? 'Развернуть навигацию' : 'Свернуть навигацию'}
        >
          {compact ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
        </button>
      </div>

      <nav className="flex flex-col gap-0.5 px-2.5 pt-3">
        {nav.map(({ to, label, icon: Icon, end }) => {
          const badge = badgeFor[to];
          return (
            <NavLink
              key={to}
              to={to}
              end={end}
              aria-label={label}
              className={({ isActive }) =>
                clsx(
                  'group flex h-8 items-center gap-2.5 rounded-md border-l-2 px-2.5 text-[13px] font-medium transition-colors',
                  compact && 'justify-center px-0',
                  isActive
                    ? 'border-l-accent bg-rail-active text-rail-text-active'
                    : 'border-l-transparent text-rail-text hover:bg-rail-hover hover:text-rail-text-active',
                )
              }
            >
              <Icon size={16} strokeWidth={1.75} className="shrink-0" />
              {!compact && <span className="flex-1 truncate">{label}</span>}
              {!compact && !!badge && (
                <span className="rounded-full bg-rail-border px-1.5 text-[10.5px] font-semibold tabular-nums text-rail-text-active">
                  {badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-rail-border px-2.5 py-2.5">
        <div className="mb-1.5">
          <SupportChat compact={compact} />
        </div>
        <div className={clsx('flex items-center gap-2 rounded-md px-1 py-1', compact && 'justify-center')}>
          <Avatar name={profileName} size="sm" />
          {!compact && (
            <div className="min-w-0 leading-tight">
              <p className="truncate text-[12.5px] font-medium text-rail-text-active">{profileName}</p>
              <p className="truncate text-[11px] text-rail-text-dim">{workspaceName}</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
