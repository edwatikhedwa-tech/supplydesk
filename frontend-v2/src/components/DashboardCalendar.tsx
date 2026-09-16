import { ChevronLeft, ChevronRight, ListTodo } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { DayButtonProps } from 'react-day-picker';
import { DayPicker } from 'react-day-picker';
import { Link } from 'react-router-dom';
import { formatCompanyName } from '../lib/format';
import type { Task } from '../lib/types';
import { DotIcon } from './ui/Badge';

const WEEKDAYS_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const MONTH_YEAR = new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' });

function dateToIso(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

function priorityTone(task: Task): string {
  if (task.priority === 'high') return 'bg-danger';
  if (task.priority === 'low') return 'bg-ink-faint';
  return 'bg-warning';
}

/** Custom day button: shows the date plus a small dot per task that day
 * (capped visually at 3) instead of react-day-picker's plain number, so a
 * busy day is recognizable at a glance without opening it. */
function TaskDayButton({ tasksByDate, ...props }: DayButtonProps & { tasksByDate: Map<string, Task[]> }) {
  const { day, modifiers, className: _className, children: _children, ...buttonProps } = props;
  const iso = dateToIso(day.date);
  const dayTasks = tasksByDate.get(iso) ?? [];
  return (
    <button
      type="button"
      {...buttonProps}
      className={`relative flex h-9 w-9 flex-col items-center justify-center rounded-full text-[13px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border ${
        modifiers.selected
          ? 'bg-accent font-semibold text-white'
          : modifiers.today
            ? 'font-semibold text-accent hover:bg-accent-subtle'
            : modifiers.outside
              ? 'text-ink-faint/50 hover:bg-surface-hover'
              : 'text-ink hover:bg-surface-hover'
      }`}
    >
      {day.date.getDate()}
      {dayTasks.length > 0 && (
        <span className="absolute bottom-1 flex gap-0.5">
          {dayTasks.slice(0, 3).map((t) => (
            <span key={t.id} className={`h-[3px] w-[3px] rounded-full ${modifiers.selected ? 'bg-white' : priorityTone(t)}`} />
          ))}
        </span>
      )}
    </button>
  );
}

/** A real, functional monthly calendar for the Dashboard, built on
 * react-day-picker (the same library shadcn/ui's own Calendar wraps) instead
 * of a hand-rolled grid -- keyboard navigation, month paging and date
 * selection all come from a maintained library. Clicking a day opens a
 * detail panel listing that day's REAL tasks (each linking to its actual
 * `/?task=<id>`), fixing the previous mini-calendar's dead links which
 * pointed at a hardcoded non-numeric placeholder id that never matched a
 * real task. */
export function DashboardCalendar({ tasks }: { tasks: Task[] }) {
  const [month, setMonth] = useState(() => new Date());
  const [selected, setSelected] = useState<Date | undefined>(() => new Date());

  const tasksByDate = useMemo(() => {
    const map = new Map<string, Task[]>();
    for (const task of tasks) {
      if (!task.due_date) continue;
      map.set(task.due_date, [...(map.get(task.due_date) ?? []), task]);
    }
    return map;
  }, [tasks]);

  const selectedIso = selected ? dateToIso(selected) : null;
  const selectedTasks = selectedIso ? (tasksByDate.get(selectedIso) ?? []) : [];
  const hasTasksMatcher = (date: Date) => tasksByDate.has(dateToIso(date));

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-3 sm:flex-row sm:gap-4 sm:p-4">
      <div className="sm:w-[300px] sm:shrink-0">
        <div className="mb-2 flex items-center justify-between px-1">
          <span className="text-[13px] font-medium capitalize text-ink">{MONTH_YEAR.format(month)}</span>
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))}
              className="flex h-6 w-6 items-center justify-center rounded text-ink-faint hover:bg-surface-hover hover:text-ink"
              aria-label="Предыдущий месяц"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              type="button"
              onClick={() => {
                const today = new Date();
                setMonth(today);
                setSelected(today);
              }}
              className="rounded px-1.5 text-[11px] text-ink-faint hover:bg-surface-hover hover:text-ink"
            >
              Сегодня
            </button>
            <button
              type="button"
              onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))}
              className="flex h-6 w-6 items-center justify-center rounded text-ink-faint hover:bg-surface-hover hover:text-ink"
              aria-label="Следующий месяц"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
        <DayPicker
          mode="single"
          month={month}
          onMonthChange={setMonth}
          selected={selected}
          onSelect={setSelected}
          showOutsideDays
          weekStartsOn={1}
          modifiers={{ hasTasks: hasTasksMatcher }}
          hideNavigation
          classNames={{
            root: 'w-full',
            month_grid: 'w-full border-collapse',
            weekdays: '',
            weekday: 'w-9 pb-1 text-center text-[11px] font-medium text-ink-faint',
            week: '',
            day: 'p-0 text-center',
            month_caption: 'sr-only',
          }}
          formatters={{ formatWeekdayName: (date) => WEEKDAYS_SHORT[(date.getDay() + 6) % 7] }}
          components={{
            DayButton: (props) => <TaskDayButton {...props} tasksByDate={tasksByDate} />,
          }}
        />
      </div>

      <div className="min-w-0 flex-1 border-t border-border pt-3 sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0">
        <p className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold capitalize text-ink">
          <ListTodo size={13} className="text-ink-muted" />
          {selected ? selected.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' }) : 'Выберите день'}
        </p>
        {selectedTasks.length > 0 ? (
          <div className="flex flex-col gap-1">
            {selectedTasks.map((task) => (
              <Link
                key={task.id}
                to={`/?task=${task.id}`}
                className="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border"
              >
                <DotIcon tone={task.priority === 'high' ? 'danger' : task.priority === 'low' ? 'neutral' : 'warning'} />
                <span className="min-w-0 flex-1">
                  <span className={`block truncate text-[12.5px] ${task.done ? 'text-ink-faint line-through' : 'text-ink'}`}>{task.title}</span>
                  {(task.supplier_name || task.request_name) && (
                    <span className="block truncate text-[11px] text-accent">
                      {task.supplier_name ? formatCompanyName(task.supplier_name) : `Заявка «${task.request_name}»`}
                    </span>
                  )}
                </span>
                {task.due_at && <span className="shrink-0 text-[10.5px] text-ink-faint">{task.due_at.slice(11, 16)}</span>}
              </Link>
            ))}
          </div>
        ) : (
          <p className="px-2 py-1.5 text-[12px] text-ink-faint">На этот день задач нет.</p>
        )}
      </div>
    </div>
  );
}
