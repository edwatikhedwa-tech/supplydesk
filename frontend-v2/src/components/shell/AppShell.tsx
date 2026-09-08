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
        <div className="flex h-11 shrink-0 items-center border-b border-border bg-surface px-4">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="flex h-7 w-full max-w-[360px] items-center gap-2 rounded-md border border-border-strong bg-canvas px-2.5 text-[12.5px] text-ink-faint hover:text-ink-soft"
          >
            <Search size={13} />
            <span className="flex-1 text-left">Заявки, поставщики, переписки, текст письма…</span>
            <kbd className="rounded border border-border-strong px-1 text-[10px] text-ink-faint">⌘K</kbd>
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
