import { CalendarDays, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Task } from '../lib/types';

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

function dateAtMidnight(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function dateToIso(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

function addDays(value: Date, days: number): Date {
  const next = dateAtMidnight(value);
  next.setDate(next.getDate() + days);
  return next;
}

function sameDay(left: Date, right: Date): boolean {
  return dateToIso(left) === dateToIso(right);
}

/** Compact month-view mini calendar for the Dashboard.
 *  `tasks` are passed from outside so the parent's reload keeps the
 *  calendar in sync after creating/editing a task. */
export function MiniCalendar({
  tasks,
}: {
  tasks: Task[];
}) {
  const [anchor, setAnchor] = useState(() => dateAtMidnight(new Date()));

  const tasksByDate = useMemo(() => {
    const map = new Map<string, number>();
    for (const task of tasks) {
      if (!task.due_date) continue;
      map.set(task.due_date, (map.get(task.due_date) ?? 0) + 1);
    }
    return map;
  }, [tasks]);

  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const gridStart = addDays(first, -(first.getDay() + 6) % 7);
  const days = Array.from({ length: 35 }, (_, index) => addDays(gridStart, index));
  const today = dateAtMidnight(new Date());

  return (
    <section className="flex flex-col rounded-lg border border-border bg-surface">
      <header className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-1.5">
          <CalendarDays size={14} className="text-ink-muted" />
          <h2 className="text-[12.5px] font-semibold text-ink">Календарь</h2>
        </div>
        <Link
          to="/calendar"
          className="flex items-center gap-0.5 text-[11.5px] font-medium text-accent hover:text-accent-hover"
        >
          Развернуть <ExternalLink size={10} />
        </Link>
      </header>

      <div className="p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[12px] font-medium text-ink">
              {MONTHS[anchor.getMonth()]} {anchor.getFullYear()}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setAnchor((d) => new Date(d.getFullYear(), d.getMonth() - 1, 1))}
                className="flex h-6 w-6 items-center justify-center rounded text-ink-faint hover:bg-surface-hover hover:text-ink"
                aria-label="Предыдущий месяц"
              >
                <ChevronLeft size={13} />
              </button>
              <button
                type="button"
                onClick={() => setAnchor(dateAtMidnight(new Date()))}
                className="h-6 rounded px-1.5 text-[10.5px] font-medium text-ink-faint hover:bg-surface-hover hover:text-ink"
              >
                Сегодня
              </button>
              <button
                type="button"
                onClick={() => setAnchor((d) => new Date(d.getFullYear(), d.getMonth() + 1, 1))}
                className="flex h-6 w-6 items-center justify-center rounded text-ink-faint hover:bg-surface-hover hover:text-ink"
                aria-label="Следующий месяц"
              >
                <ChevronRight size={13} />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-7 gap-px">
            {WEEKDAYS.map((wd) => (
              <span
                key={wd}
                className="pb-1 text-center text-[9px] font-semibold uppercase tracking-wide text-ink-faint"
              >
                {wd}
              </span>
            ))}
            {days.map((day) => {
              const iso = dateToIso(day);
              const count = tasksByDate.get(iso) ?? 0;
              const isToday = sameDay(day, today);
              const currentMonth = day.getMonth() === anchor.getMonth();
              return (
                <Link
                  key={iso}
                  to={`/?task=${count > 0 ? 'any' : ''}`}
                  aria-label={`${day.getDate()} ${MONTHS[day.getMonth()]}${count > 0 ? `, ${count} задач` : ''}`}
                  className={`relative flex h-8 items-center justify-center rounded-md text-[11.5px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border ${
                    isToday
                      ? 'bg-accent font-semibold text-white'
                      : currentMonth
                        ? 'text-ink-soft hover:bg-surface-hover'
                        : 'text-ink-faint'
                  }`}
                >
                  {day.getDate()}
                  {count > 0 && !isToday && (
                    <span className="absolute bottom-0.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-accent" />
                  )}
                  {count > 0 && isToday && (
                    <span className="absolute bottom-0.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-white" />
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      </section>
  );
}