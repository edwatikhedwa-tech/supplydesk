import { Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { CommandPalette } from './CommandPalette';
import { Sidebar } from './Sidebar';

export function AppShell() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-canvas text-ink">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex h-14 shrink-0 items-center border-b border-border bg-surface px-3 sm:px-4">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="flex h-9 w-full max-w-[620px] items-center gap-2 rounded-lg border border-border-strong bg-canvas px-3 text-[13px] text-ink-faint transition-colors hover:border-accent-border hover:text-ink-soft"
          >
            <Search size={14} className="shrink-0" />
            <span className="min-w-0 flex-1 truncate whitespace-nowrap text-left">
              <span className="sm:hidden">Поиск…</span>
              <span className="hidden sm:inline">Поиск: заявки, поставщики, переписки, текст письма…</span>
            </span>
            <kbd className="hidden shrink-0 rounded border border-border-strong px-1.5 py-0.5 text-[10px] text-ink-faint sm:inline">⌘K</kbd>
          </button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <Outlet />
        </div>
      </main>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
