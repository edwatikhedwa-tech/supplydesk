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
import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/AuthContext';
import { useApiData } from '../../lib/useApiData';
import { Avatar } from '../ui/Avatar';

const nav = [
  { to: '/', label: 'Дашборд', icon: LayoutGrid, end: true },
  { to: '/requests', label: 'Заявки', icon: ListChecks },
  { to: '/suppliers', label: 'Поставщики', icon: Truck },
  { to: '/messages', label: 'Сообщения', icon: Inbox },
  { to: '/blacklist', label: 'Чёрный список', icon: Ban },
  { to: '/settings', label: 'Настройки', icon: Settings },
];

function useNavCounts() {
  const dashboard = useApiData(() => api.dashboardSummary(), []);
  const threads = useApiData(() => api.listThreads().then((r) => r.items), []);
  const attention = dashboard.status === 'ready' ? dashboard.data.kpis.attention : 0;
  const unread = threads.status === 'ready' ? threads.data.reduce((sum, t) => sum + t.unread_count, 0) : 0;
  return { attention, unread };
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const { user } = useAuth();
  const { attention, unread } = useNavCounts();
  const badgeFor: Record<string, number> = { '/requests': attention, '/messages': unread };

  return (
    <aside
      className={clsx(
        'flex h-full shrink-0 flex-col bg-rail transition-[width] duration-150',
        collapsed ? 'w-[64px]' : 'w-[224px]',
      )}
    >
      <div className={clsx('flex h-14 items-center border-b border-rail-border', collapsed ? 'justify-center px-0' : 'justify-between px-4')}>
        {!collapsed && (
          <span className="font-display text-[15px] font-semibold tracking-tight text-rail-text-active">
            SupplyDesk
          </span>
        )}
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="flex h-7 w-7 items-center justify-center rounded-md text-rail-text-dim hover:bg-rail-hover hover:text-rail-text-active"
          aria-label={collapsed ? 'Развернуть навигацию' : 'Свернуть навигацию'}
        >
          {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
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
              className={({ isActive }) =>
                clsx(
                  'group flex h-8 items-center gap-2.5 rounded-md border-l-2 px-2.5 text-[13px] font-medium transition-colors',
                  collapsed && 'justify-center px-0',
                  isActive
                    ? 'border-l-accent bg-rail-active text-rail-text-active'
                    : 'border-l-transparent text-rail-text hover:bg-rail-hover hover:text-rail-text-active',
                )
              }
            >
              <Icon size={16} strokeWidth={1.75} className="shrink-0" />
              {!collapsed && <span className="flex-1 truncate">{label}</span>}
              {!collapsed && !!badge && (
                <span className="rounded-full bg-rail-border px-1.5 text-[10.5px] font-semibold tabular-nums text-rail-text-active">
                  {badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-rail-border px-2.5 py-2.5">
        <div className={clsx('flex items-center gap-2 rounded-md px-1 py-1', collapsed && 'justify-center')}>
          <Avatar name={user?.display_name ?? '?'} size="sm" />
          {!collapsed && (
            <div className="min-w-0 leading-tight">
              <p className="truncate text-[12.5px] font-medium text-rail-text-active">{user?.display_name}</p>
              <p className="truncate text-[11px] text-rail-text-dim">{user?.workspace_name}</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
