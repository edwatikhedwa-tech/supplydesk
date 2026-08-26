import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { BarChart3, Ban, ClipboardList, LogOut, Menu, MessageSquare, PackageSearch, Settings as SettingsIcon, X } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { getInitials } from '@/lib/utils';

const items = [
  { label: 'Дашборд', to: '/', icon: BarChart3, enabled: true },
  { label: 'Мои заявки', to: '/requests', icon: ClipboardList, enabled: true },
  { label: 'Переписка', to: '/messages', icon: MessageSquare, enabled: true },
  { label: 'Поставщики', to: '/suppliers', icon: PackageSearch, enabled: true },
  { label: 'Чёрный список', to: '/blacklist', icon: Ban, enabled: true },
  { label: 'Настройки', to: '/settings', icon: SettingsIcon, enabled: true },
];

export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const sidebarContent = (
    <>
      <button onClick={() => navigate('/')} className="flex h-[76px] items-center border-b border-ink-100 px-7 text-left">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-600 text-xl font-bold text-white shadow-soft">›</span>
        <span className="ml-3">
          <span className="block text-[15px] font-bold tracking-tight">SupplyDesk</span>
          <span className="block text-[10px] font-medium uppercase tracking-[0.16em] text-ink-500">Procurement OS</span>
        </span>
      </button>
      <nav className="flex-1 space-y-1 px-4 py-7">
        <div className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-ink-500">Рабочее пространство</div>
        {items.map(({ label, to, icon: Icon, enabled }) =>
          enabled ? (
            <NavLink key={label} to={to} end={to === '/'} className={({ isActive }) => `group flex items-center gap-3 rounded-xl px-3 py-3 text-[13px] font-semibold transition-all ${isActive ? 'bg-accent-50 text-accent-700' : 'text-ink-500 hover:bg-ink-50 hover:text-ink-800'}`}>
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ) : (
            <div key={label} className="flex cursor-not-allowed items-center gap-3 rounded-xl px-3 py-3 text-[13px] font-semibold text-ink-300">
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
              <span className="ml-auto text-[9px] font-bold uppercase tracking-wider">скоро</span>
            </div>
          )
        )}
      </nav>
      <div className="border-t border-ink-100 p-4">
        <div className="flex items-center gap-3 rounded-xl px-3 py-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-100 text-xs font-bold text-accent-700">
            {getInitials(user?.display_name || user?.email || '?')}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-bold text-ink-800">{user?.display_name || user?.email}</div>
            <div className="truncate text-[11px] text-ink-500">{user?.workspace_name}</div>
          </div>
          <button
            onClick={handleLogout}
            title="Выйти"
            aria-label="Выйти"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-400 transition hover:bg-rose-50 hover:text-rose-600"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-ink-50 text-ink-900">
      {/* Mobile top bar — the only way to reach navigation below the lg breakpoint,
          since the real sidebar is hidden there (see S-01 in the defect ledger). */}
      <div className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-ink-200/80 bg-white px-4 lg:hidden">
        <button
          onClick={() => setMobileOpen(true)}
          aria-label="Открыть меню"
          className="flex h-10 w-10 items-center justify-center rounded-lg text-ink-600 hover:bg-ink-100"
        >
          <Menu size={20} />
        </button>
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-600 text-sm font-bold text-white">›</span>
        <span className="text-sm font-bold tracking-tight">SupplyDesk</span>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-ink-900/30 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[248px] flex-col border-r border-ink-200/80 bg-white transition-transform duration-200 lg:z-20 lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <button
          onClick={() => setMobileOpen(false)}
          aria-label="Закрыть меню"
          className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-lg text-ink-400 hover:bg-ink-100 lg:hidden"
        >
          <X size={18} />
        </button>
        {sidebarContent}
      </aside>
      <main className="lg:pl-[248px]">
        <Outlet />
      </main>
    </div>
  );
}
