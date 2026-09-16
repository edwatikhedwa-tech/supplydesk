import { CalendarDays, ChevronLeft, ChevronRight, ListTodo } from 'lucide-react';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge, DotIcon } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { api } from '../lib/api';
import { formatCompanyName } from '../lib/format';
import { formatTaskDeadline } from '../lib/taskSchedule';
import { formatTaskReminder } from '../lib/taskSchedule';
import type { Task } from '../lib/types';
import { useApiData } from '../lib/useApiData';

type CalendarView = 'month' | 'week' | 'agenda' | 'upcoming' | 'today';

const VIEW_LABELS: Record<CalendarView, string> = {
  month: 'Месяц',
  week: 'Неделя',
  agenda: 'Повестка',
  upcoming: 'Скоро',
  today: 'Сегодня',
};

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

function isoToDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function addDays(value: Date, days: number): Date {
  const next = dateAtMidnight(value);
  next.setDate(next.getDate() + days);
  return next;
}

function startOfWeek(value: Date): Date {
  return addDays(value, -(value.getDay() + 6) % 7);
}

function sameDay(left: Date, right: Date): boolean {
  return dateToIso(left) === dateToIso(right);
}

function dateLabel(iso: string): string {
  return isoToDate(iso).toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });
}

function priorityTone(task: Task): 'danger' | 'warning' | 'neutral' {
  if (task.priority === 'high') return 'danger';
  if (task.priority === 'low') return 'neutral';
  return 'warning';
}

function TaskLink({ task, compact = false, dense = false, fullContext = false }: { task: Task; compact?: boolean; dense?: boolean; fullContext?: boolean }) {
  const deadline = formatTaskDeadline(task);
  const reminderLabel = task.reminders.length > 0 ? ` Напоминание: ${formatTaskReminder(task.reminders[0])}.` : '';
  const contextLabel = task.supplier_name ? `Компания: ${task.supplier_name}` : task.request_name ? `Заявка: ${task.request_name}` : '';
  // In a narrow month cell the company itself is more useful than a repeated
  // "Компания:" prefix. The full relation is retained in accessible text and
  // the native tooltip above.
  const contextDisplay = task.supplier_name ? formatCompanyName(task.supplier_name) : task.request_name ? `Заявка: ${task.request_name}` : '';
  return (
    <Link
      to={`/?task=${task.id}`}
      aria-label={`${task.title}. ${contextLabel ? `${contextLabel}. ` : ''}${deadline}.${reminderLabel}`}
      title={contextLabel || task.title}
      className={compact
        ? `flex min-w-0 items-center gap-1 rounded-md px-1.5 py-1 text-left text-[11px] text-ink-soft hover:bg-accent-subtle hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border ${dense ? 'max-[500px]:justify-center max-[500px]:px-1' : ''}`
        : 'flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-2.5 text-left hover:border-accent-border hover:bg-accent-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border'}
    >
      <DotIcon tone={priorityTone(task)} />
      <span className={compact ? `min-w-0 truncate ${dense ? 'max-[500px]:sr-only' : ''}` : 'min-w-0 flex-1'}>
        <span className="block truncate">{task.title}</span>
        {contextDisplay && <span className={`block text-[10px] font-medium text-accent ${fullContext ? 'whitespace-normal break-words' : 'truncate'}`}>{contextDisplay}</span>}
      </span>
      {!compact && <span className="shrink-0 text-right text-[11px] text-ink-faint"><span className="block">{deadline}</span>{task.reminders.length > 0 && <span className="block">{formatTaskReminder(task.reminders[0])}</span>}</span>}
    </Link>
  );
}

function EmptyCalendar({ label }: { label: string }) {
  return <EmptyState icon={CalendarDays} title={label} description="Добавьте дату задаче на Дашборде — она появится здесь." />;
}

function MonthView({
  anchor,
  tasks,
  selectedDate,
  onSelectDate,
}: {
  anchor: Date;
  tasks: Task[];
  selectedDate: string;
  onSelectDate: (date: string) => void;
}) {
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const gridStart = addDays(first, -(first.getDay() + 6) % 7);
  const days = Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));
  const tasksByDate = new Map<string, Task[]>();
  for (const task of tasks) {
    if (!task.due_date) continue;
    tasksByDate.set(task.due_date, [...(tasksByDate.get(task.due_date) ?? []), task]);
  }
  const today = dateAtMidnight(new Date());

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div>
        <div className="grid grid-cols-7 border-b border-border bg-canvas">
          {WEEKDAYS.map((weekday) => <span key={weekday} className="px-1 py-2 text-center text-[9px] font-semibold uppercase tracking-wide text-ink-faint sm:px-2 sm:text-[10.5px]">{weekday}</span>)}
        </div>
        <div className="grid grid-cols-7" role="grid" aria-label={`${MONTHS[anchor.getMonth()]} ${anchor.getFullYear()}`}>
          {days.map((day) => {
            const iso = dateToIso(day);
            const dayTasks = tasksByDate.get(iso) ?? [];
            const currentMonth = day.getMonth() === anchor.getMonth();
            const isToday = sameDay(day, today);
            return (
              <section key={iso} role="gridcell" aria-label={`${dateLabel(iso)}: ${dayTasks.length} задач`} className="min-h-[76px] border-b border-r border-border p-1 last:border-r-0 sm:min-h-[108px] sm:p-1.5">
                <div className="mb-0.5 flex justify-end sm:mb-1">
                  <button
                    type="button"
                    onClick={() => onSelectDate(iso)}
                    aria-label={`Показать задачи: ${dateLabel(iso)}`}
                    aria-pressed={selectedDate === iso}
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border ${isToday ? 'bg-accent text-white' : selectedDate === iso ? 'bg-accent-subtle text-accent' : currentMonth ? 'text-ink-soft hover:bg-surface-hover' : 'text-ink-faint hover:bg-surface-hover'}`}
                  >
                    {day.getDate()}
                  </button>
                </div>
                {dayTasks.slice(0, 2).map((task) => <TaskLink key={task.id} task={task} compact dense />)}
                {dayTasks.length > 2 && <Link to={`/?task=${dayTasks[2].id}`} className="block px-1.5 pt-0.5 text-[10.5px] font-medium text-accent hover:text-accent-hover">+ ещё {dayTasks.length - 2}</Link>}
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function WeekView({ anchor, tasks }: { anchor: Date; tasks: Task[] }) {
  const week = Array.from({ length: 7 }, (_, index) => addDays(startOfWeek(anchor), index));
  const today = dateAtMidnight(new Date());

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-7">
      {week.map((day) => {
        const iso = dateToIso(day);
        const dayTasks = tasks.filter((task) => task.due_date === iso);
        const isToday = sameDay(day, today);
        return (
          <section key={iso} className={`min-h-[132px] rounded-lg border p-2.5 ${isToday ? 'border-accent-border bg-accent-subtle' : 'border-border bg-surface'}`}>
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-[11px] font-medium text-ink-muted">{WEEKDAYS[(day.getDay() + 6) % 7]}</p>
              <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold ${isToday ? 'bg-accent text-white' : 'text-ink-soft'}`}>{day.getDate()}</span>
            </div>
            <div className="flex flex-col gap-1">
              {dayTasks.map((task) => <TaskLink key={task.id} task={task} compact />)}
              {dayTasks.length === 0 && <p className="pt-3 text-[11px] text-ink-faint">Нет задач</p>}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function AgendaView({ tasks, title }: { tasks: Task[]; title: string }) {
  const groups = new Map<string, Task[]>();
  for (const task of tasks) {
    if (!task.due_date) continue;
    groups.set(task.due_date, [...(groups.get(task.due_date) ?? []), task]);
  }
  const entries = [...groups.entries()].sort(([left], [right]) => left.localeCompare(right));
  if (entries.length === 0) return <EmptyCalendar label={title} />;

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      {entries.map(([date, dateTasks]) => (
        <section key={date} className="rounded-lg border border-border bg-surface">
          <header className="flex items-center justify-between border-b border-border px-3 py-2.5">
            <h2 className="capitalize text-[12.5px] font-semibold text-ink">{dateLabel(date)}</h2>
            <Badge tone="neutral">{dateTasks.length}</Badge>
          </header>
          <div className="flex flex-col gap-1.5 p-2">{dateTasks.map((task) => <TaskLink key={task.id} task={task} />)}</div>
        </section>
      ))}
    </div>
  );
}

export function Calendar() {
  const state = useApiData(() => api.listTasks().then((result) => result.items), []);
  const [view, setView] = useState<CalendarView>('month');
  const [anchor, setAnchor] = useState(() => dateAtMidnight(new Date()));
  const [selectedDate, setSelectedDate] = useState(() => dateToIso(new Date()));

  if (state.status === 'loading') {
    return <div className="flex h-full flex-col overflow-auto"><PageHeader title="Календарь" /><LoadingState label="Загружаем задачи…" /></div>;
  }
  if (state.status === 'error') {
    return <div className="flex h-full flex-col overflow-auto"><PageHeader title="Календарь" /><ErrorState message={state.message} onRetry={state.reload} /></div>;
  }

  const datedTasks = state.data.filter((task) => Boolean(task.due_date));
  const todayIso = dateToIso(new Date());
  const todayTasks = datedTasks.filter((task) => task.due_date === todayIso);
  const upcomingTasks = datedTasks.filter((task) => task.due_date! >= todayIso);
  const overdueTasks = datedTasks.filter((task) => task.due_date! < todayIso);
  const anchorLabel = view === 'week'
    ? `${dateToIso(startOfWeek(anchor)).slice(8)}–${dateToIso(addDays(startOfWeek(anchor), 6)).slice(8)} ${anchor.getFullYear()}`
    : `${MONTHS[anchor.getMonth()]} ${anchor.getFullYear()}`;
  const shift = (amount: number) => setAnchor((current) => view === 'week' ? addDays(current, amount * 7) : new Date(current.getFullYear(), current.getMonth() + amount, 1));

  let content: ReactNode;
  if (view === 'month') {
    const selectedTasks = datedTasks.filter((task) => task.due_date === selectedDate);
    content = (
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
        <div className="min-w-0 flex-1">
          <MonthView anchor={anchor} tasks={datedTasks} selectedDate={selectedDate} onSelectDate={setSelectedDate} />
        </div>
        {/* Persistent day-detail sidebar on desktop (matches the shadcn
         * monthly-view reference: grid + always-visible selected-day event
         * list), collapsing to a panel below the grid on narrow screens. */}
        <section className="rounded-lg border border-border bg-surface p-2 lg:w-[280px] lg:shrink-0" aria-label={`Задачи на ${dateLabel(selectedDate)}`}>
          <p className="px-1 pb-2 text-[11.5px] font-semibold capitalize text-ink">{dateLabel(selectedDate)}</p>
          {selectedTasks.length > 0 ? (
            <div className="flex flex-col gap-1.5">{selectedTasks.map((task) => <TaskLink key={task.id} task={task} fullContext />)}</div>
          ) : (
            <p className="px-1 pb-1 text-[11.5px] text-ink-faint">Задач нет</p>
          )}
        </section>
      </div>
    );
  }
  else if (view === 'week') content = <WeekView anchor={anchor} tasks={datedTasks} />;
  else if (view === 'today') content = <AgendaView tasks={todayTasks} title="На сегодня задач нет" />;
  else if (view === 'upcoming') content = <AgendaView tasks={[...overdueTasks, ...upcomingTasks]} title="Ближайших задач нет" />;
  else content = <AgendaView tasks={datedTasks} title="Датированных задач нет" />;

  return (
    <div className="flex h-full flex-col overflow-auto">
      <PageHeader
        title="Календарь"
        description="Только датированные личные задачи. Настроить напоминание можно при создании задачи."
        actions={<Link to="/" className="inline-flex h-8 items-center gap-1.5 rounded-[10px] border border-border-strong bg-surface px-3 text-[12px] font-medium text-ink hover:bg-surface-hover"><ListTodo size={13} /> Задачи</Link>}
      />
      <main className="flex flex-col gap-4 px-4 pb-6 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-2">
          <div className="flex flex-wrap gap-1" role="toolbar" aria-label="Представление календаря">
            {(Object.keys(VIEW_LABELS) as CalendarView[]).map((option) => (
              <button key={option} type="button" onClick={() => setView(option)} aria-pressed={view === option} className={`h-8 rounded-md px-2.5 text-[12px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border ${view === option ? 'bg-accent text-white' : 'text-ink-muted hover:bg-surface-hover hover:text-ink'}`}>{VIEW_LABELS[option]}</button>
            ))}
          </div>
          {(view === 'month' || view === 'week') && (
            <div className="flex items-center gap-1">
              <button type="button" onClick={() => shift(-1)} className="flex h-8 w-8 items-center justify-center rounded-md text-ink-muted hover:bg-surface-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border" aria-label={view === 'week' ? 'Предыдущая неделя' : 'Предыдущий месяц'}><ChevronLeft size={15} /></button>
              <button type="button" onClick={() => setAnchor(dateAtMidnight(new Date()))} className="h-8 rounded-md px-2.5 text-[12px] font-medium text-ink-muted hover:bg-surface-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border">Сегодня</button>
              <button type="button" onClick={() => shift(1)} className="flex h-8 w-8 items-center justify-center rounded-md text-ink-muted hover:bg-surface-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border" aria-label={view === 'week' ? 'Следующая неделя' : 'Следующий месяц'}><ChevronRight size={15} /></button>
            </div>
          )}
        </div>
        {(view === 'month' || view === 'week') && <div className="flex items-center justify-between gap-3"><h2 className="font-display text-[16px] font-semibold text-ink">{anchorLabel}</h2><span className="text-[11.5px] text-ink-faint">{datedTasks.length} с датой</span></div>}
        {content}
        {state.data.length > datedTasks.length && <p className="text-[11.5px] text-ink-faint">Без срока: {state.data.length - datedTasks.length}. Они остаются в списке задач и не создают календарное событие.</p>}
      </main>
    </div>
  );
}
