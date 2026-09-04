import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Flag } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ThreadPriority = 1 | 2 | 3 | null;

interface ThreadMetadataControlsProps {
  important: boolean;
  priority: ThreadPriority;
  onChange: (patch: { important?: boolean; priority?: ThreadPriority }) => Promise<void>;
  compact?: boolean;
}

const PRIORITY_LABELS: Record<Exclude<ThreadPriority, null>, string> = {
  1: 'Приоритет 1 — высокий',
  2: 'Приоритет 2 — обычный',
  3: 'Приоритет 3 — низкий',
};

export function ThreadMetadataControls({ important, priority, onChange, compact = true }: ThreadMetadataControlsProps) {
  const [localImportant, setLocalImportant] = useState(important);
  const [localPriority, setLocalPriority] = useState<ThreadPriority>(priority);
  const [menuOpen, setMenuOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLocalImportant(important);
    setLocalPriority(priority);
  }, [important, priority]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const closeOnOutside = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('pointerdown', closeOnOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [menuOpen]);

  const commit = async (patch: { important?: boolean; priority?: ThreadPriority }) => {
    const previousImportant = localImportant;
    const previousPriority = localPriority;
    if (patch.important !== undefined) setLocalImportant(patch.important);
    if (patch.priority !== undefined) setLocalPriority(patch.priority);
    setBusy(true);
    setError('');
    try {
      await onChange(patch);
    } catch (err) {
      setLocalImportant(previousImportant);
      setLocalPriority(previousPriority);
      setError(err instanceof Error ? err.message : 'Не удалось сохранить метаданные.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex shrink-0 items-center gap-0.5" onClick={(event) => event.stopPropagation()}>
      <button
        type="button"
        disabled={busy}
        aria-label={localImportant ? 'Снять отметку важности' : 'Отметить как важное'}
        aria-pressed={localImportant}
        title={localImportant ? 'Важное письмо' : 'Отметить как важное'}
        onClick={() => void commit({ important: !localImportant })}
        className={cn(
          'inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400 disabled:cursor-wait disabled:opacity-50',
          localImportant ? 'bg-amber-50 text-amber-700 ring-1 ring-amber-200' : 'text-ink-400 hover:bg-ink-100 hover:text-ink-700',
        )}
      >
        <Flag size={15} fill={localImportant ? 'currentColor' : 'none'} aria-hidden="true" />
        {!compact && <span className="ml-1.5 text-xs font-semibold">Важное</span>}
      </button>

      <div ref={menuRef} className="relative">
        <button
          type="button"
          disabled={busy}
          aria-label={priority == null ? 'Выбрать приоритет' : PRIORITY_LABELS[priority]}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          title={priority == null ? 'Без приоритета' : PRIORITY_LABELS[priority]}
          onClick={() => setMenuOpen((open) => !open)}
          className={cn(
            'inline-flex min-h-9 min-w-9 items-center justify-center gap-0.5 rounded-lg px-1.5 text-xs font-bold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400 disabled:cursor-wait disabled:opacity-50',
            priority == null ? 'text-ink-400 hover:bg-ink-100 hover:text-ink-700' : 'bg-accent-50 text-accent-700 ring-1 ring-accent-200',
          )}
        >
          {priority ?? '—'}
          <ChevronDown size={12} aria-hidden="true" />
        </button>
        {menuOpen && (
          <div role="menu" aria-label="Приоритет письма" className="absolute right-0 top-full z-30 mt-1 min-w-48 rounded-xl border border-ink-200 bg-white p-1.5 shadow-xl">
            <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); void commit({ priority: null }); }} className={cn('flex min-h-10 w-full items-center rounded-lg px-2.5 text-left text-xs font-medium hover:bg-ink-50', priority == null ? 'text-accent-700' : 'text-ink-700')}>Без приоритета</button>
            {([1, 2, 3] as const).map((value) => (
              <button key={value} type="button" role="menuitemradio" aria-checked={priority === value} onClick={() => { setMenuOpen(false); void commit({ priority: value }); }} className={cn('flex min-h-10 w-full items-center gap-2 rounded-lg px-2.5 text-left text-xs font-medium hover:bg-ink-50', priority === value ? 'text-accent-700' : 'text-ink-700')}>
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-ink-100 text-2xs font-bold">{value}</span>
                {PRIORITY_LABELS[value].replace(`Приоритет ${value} — `, '')}
              </button>
            ))}
          </div>
        )}
      </div>
      {error && <span role="alert" className="sr-only">{error}</span>}
    </div>
  );
}
