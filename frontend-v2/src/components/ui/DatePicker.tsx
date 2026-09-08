import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

function toIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function fromIso(iso: string): Date | null {
  if (!iso) return null;
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function formatDisplay(iso: string): string {
  const d = fromIso(iso);
  if (!d) return '';
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Small popover calendar -- replaces the native `<input type="date">`, whose
 * browser-chrome look doesn't match the rest of the UI and can't be styled. */
export function DatePicker({
  value,
  onChange,
  placeholder = 'Выберите дату…',
  className,
  size = 'md',
}: {
  value: string;
  onChange: (iso: string) => void;
  placeholder?: string;
  className?: string;
  size?: 'sm' | 'md';
}) {
  const [open, setOpen] = useState(false);
  const selected = fromIso(value);
  const [viewMonth, setViewMonth] = useState(() => selected ?? new Date());
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  useEffect(() => {
    if (open) setViewMonth(selected ?? new Date());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const year = viewMonth.getFullYear();
  const month = viewMonth.getMonth();
  const firstOfMonth = new Date(year, month, 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7; // Monday-first grid
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();

  const cells: (Date | null)[] = [...Array(startOffset).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => new Date(year, month, i + 1))];

  return (
    <div ref={rootRef} className={`relative ${className ?? ''}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`flex w-full items-center gap-2 rounded-md border border-border-strong bg-surface px-2.5 text-left outline-none focus:border-accent focus:ring-1 focus:ring-accent-border ${
          size === 'sm' ? 'h-7 text-[12px]' : 'h-8 text-[12.5px]'
        }`}
      >
        <CalendarDays size={13} className="shrink-0 text-ink-faint" />
        <span className={value ? 'truncate text-ink' : 'truncate text-ink-faint'}>{value ? formatDisplay(value) : placeholder}</span>
      </button>

      {open && (
        <div className="absolute left-0 top-[calc(100%+4px)] z-30 w-[240px] rounded-lg border border-border bg-surface p-2.5 shadow-lg">
          <div className="mb-1.5 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setViewMonth(new Date(year, month - 1, 1))}
              className="flex h-6 w-6 items-center justify-center rounded-md text-ink-muted hover:bg-surface-hover hover:text-ink"
              aria-label="Предыдущий месяц"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="text-[12.5px] font-medium text-ink">
              {MONTHS[month]} {year}
            </span>
            <button
              type="button"
              onClick={() => setViewMonth(new Date(year, month + 1, 1))}
              className="flex h-6 w-6 items-center justify-center rounded-md text-ink-muted hover:bg-surface-hover hover:text-ink"
              aria-label="Следующий месяц"
            >
              <ChevronRight size={14} />
            </button>
          </div>

          <div className="grid grid-cols-7 gap-0.5 text-center">
            {WEEKDAYS.map((w) => (
              <span key={w} className="py-1 text-[10px] font-medium text-ink-faint">
                {w}
              </span>
            ))}
            {cells.map((d, i) => {
              if (!d) return <span key={i} />;
              const iso = toIso(d);
              const isSelected = value === iso;
              const isToday = toIso(today) === iso;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    onChange(iso);
                    setOpen(false);
                  }}
                  className={`flex h-7 w-7 items-center justify-center rounded-md text-[12px] transition-colors ${
                    isSelected
                      ? 'bg-accent font-semibold text-white'
                      : isToday
                        ? 'font-semibold text-accent hover:bg-accent-subtle'
                        : 'text-ink-soft hover:bg-surface-hover'
                  }`}
                >
                  {d.getDate()}
                </button>
              );
            })}
          </div>

          <div className="mt-1.5 flex items-center justify-between border-t border-border pt-1.5">
            <button
              type="button"
              onClick={() => {
                onChange(toIso(new Date()));
                setOpen(false);
              }}
              className="rounded-md px-2 py-1 text-[11.5px] font-medium text-accent hover:bg-accent-subtle"
            >
              Сегодня
            </button>
            {value && (
              <button
                type="button"
                onClick={() => {
                  onChange('');
                  setOpen(false);
                }}
                className="rounded-md px-2 py-1 text-[11.5px] text-ink-muted hover:bg-surface-hover"
              >
                Очистить
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
