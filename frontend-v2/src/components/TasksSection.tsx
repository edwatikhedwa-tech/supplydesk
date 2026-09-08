import { Check, ListTodo, Plus, Trash2, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { formatCompanyName, formatDeadline } from '../lib/format';
import type { Task } from '../lib/types';
import { useApiData } from '../lib/useApiData';
import { Button } from './ui/Button';
import { DatePicker } from './ui/DatePicker';
import { EmptyState } from './ui/EmptyState';
import { ErrorState, LoadingState } from './ui/ErrorState';
import { TaskSupplierPreview } from './TaskSupplierPreview';

/** Dashboard's "Мои задачи" block (§2, §12 of the concept doc) -- a
 * deliberately separate entity from the system-detected "Требует внимания"
 * cards above it: those are events SupplyDesk noticed on its own, tasks are
 * things the owner decided to do. */
export function TasksSection() {
  const state = useApiData(() => api.listTasks().then((r) => r.items), []);
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const groups = useMemo(() => {
    if (state.status !== 'ready') return null;
    const overdue: typeof state.data = [];
    const today: typeof state.data = [];
    const upcoming: typeof state.data = [];
    const noDate: typeof state.data = [];
    const todayIso = new Date().toISOString().slice(0, 10);
    for (const t of state.data) {
      if (!t.due_date) noDate.push(t);
      else if (t.due_date < todayIso) overdue.push(t);
      else if (t.due_date === todayIso) today.push(t);
      else upcoming.push(t);
    }
    return { overdue, today, upcoming: [...upcoming, ...noDate] };
  }, [state]);

  async function addTask() {
    if (!title.trim()) return;
    setSubmitting(true);
    try {
      await api.createTask({ title: title.trim(), due_date: dueDate || undefined });
      setTitle('');
      setDueDate('');
      setAdding(false);
      state.reload();
    } catch {
      // Kept simple: the add form stays open with the text intact so nothing is lost.
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleDone(taskId: number, done: boolean) {
    setBusyId(taskId);
    try {
      await api.setTaskDone(taskId, done);
      state.reload();
    } finally {
      setBusyId(null);
    }
  }

  async function remove(taskId: number) {
    setBusyId(taskId);
    try {
      await api.deleteTask(taskId);
      state.reload();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="flex flex-col rounded-lg border border-border bg-surface">
      <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <ListTodo size={14} className="text-ink-muted" />
          <h2 className="text-[12.5px] font-semibold text-ink">Мои задачи</h2>
          {groups && <span className="tabular-nums text-[11.5px] text-ink-faint">{groups.overdue.length + groups.today.length + groups.upcoming.length}</span>}
        </div>
        <Button variant="ghost" size="sm" icon={<Plus size={13} />} onClick={() => setAdding((v) => !v)}>
          Задача
        </Button>
      </header>

      {adding && (
        <div className="flex items-center gap-1.5 border-b border-border px-4 py-2.5">
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void addTask()}
            placeholder="Например: позвонить поставщику завтра в 11:00"
            className="h-8 flex-1 rounded-md border border-border-strong bg-canvas px-2.5 text-[12.5px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
          <DatePicker value={dueDate} onChange={setDueDate} className="w-[160px]" />
          <Button variant="primary" size="sm" disabled={!title.trim() || submitting} onClick={() => void addTask()}>
            Добавить
          </Button>
          <button type="button" onClick={() => setAdding(false)} className="flex h-8 w-8 items-center justify-center rounded-md text-ink-faint hover:bg-surface-hover">
            <X size={14} />
          </button>
        </div>
      )}

      {state.status === 'loading' ? (
        <LoadingState label="Загружаем задачи…" />
      ) : state.status === 'error' ? (
        <ErrorState message={state.message} onRetry={state.reload} />
      ) : !groups || (groups.overdue.length === 0 && groups.today.length === 0 && groups.upcoming.length === 0) ? (
        <EmptyState icon={ListTodo} title="Задач нет" description="Добавьте то, что нужно сделать — звонок, уточнение, письмо." />
      ) : (
        <div className="flex flex-col">
          {groups.overdue.length > 0 && (
            <TaskGroup
              label="Просрочено"
              tone="text-danger"
              tasks={groups.overdue}
              busyId={busyId}
              expandedId={expandedId}
              onExpand={setExpandedId}
              onToggle={toggleDone}
              onDelete={remove}
            />
          )}
          {groups.today.length > 0 && (
            <TaskGroup
              label="Сегодня"
              tone="text-warning"
              tasks={groups.today}
              busyId={busyId}
              expandedId={expandedId}
              onExpand={setExpandedId}
              onToggle={toggleDone}
              onDelete={remove}
            />
          )}
          {groups.upcoming.length > 0 && (
            <TaskGroup
              label="Скоро"
              tone="text-ink-muted"
              tasks={groups.upcoming}
              busyId={busyId}
              expandedId={expandedId}
              onExpand={setExpandedId}
              onToggle={toggleDone}
              onDelete={remove}
            />
          )}
        </div>
      )}
    </section>
  );
}

function TaskGroup({
  label,
  tone,
  tasks,
  busyId,
  expandedId,
  onExpand,
  onToggle,
  onDelete,
}: {
  label: string;
  tone: string;
  tasks: Task[];
  busyId: number | null;
  expandedId: number | null;
  onExpand: (id: number | null) => void;
  onToggle: (id: number, done: boolean) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div>
      <p className={`px-4 pt-2.5 text-[10.5px] font-semibold uppercase tracking-wide ${tone}`}>{label}</p>
      {tasks.map((t) => (
        <div key={t.id} className="border-b border-border px-4 py-2 last:border-0 hover:bg-surface-hover">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              disabled={busyId === t.id}
              onClick={() => onToggle(t.id, true)}
              aria-label="Отметить выполненной"
              className="flex h-4 w-4 shrink-0 items-center justify-center rounded border border-border-strong text-transparent hover:border-accent hover:text-accent"
            >
              <Check size={11} />
            </button>
            <button
              type="button"
              disabled={!t.supplier_id}
              onClick={() => onExpand(expandedId === t.id ? null : t.id)}
              className="min-w-0 flex-1 text-left disabled:cursor-default"
            >
              <p className="truncate text-[12.5px] text-ink">{t.title}</p>
              {(t.request_id || t.supplier_id) && (
                <p className="truncate text-[11px] text-ink-faint">
                  {t.request_id && (
                    <Link to={`/requests/${t.request_id}`} className="hover:text-accent" onClick={(e) => e.stopPropagation()}>
                      {t.request_name}
                    </Link>
                  )}
                  {t.supplier_id && (
                    <Link to={`/suppliers/${t.supplier_id}`} className="hover:text-accent" onClick={(e) => e.stopPropagation()}>
                      {formatCompanyName(t.supplier_name ?? '')}
                    </Link>
                  )}
                </p>
              )}
            </button>
            {t.due_date && <span className="shrink-0 text-[11px] text-ink-faint">{formatDeadline(t.due_date)}</span>}
            <button
              type="button"
              disabled={busyId === t.id}
              onClick={() => onDelete(t.id)}
              aria-label="Удалить задачу"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-ink-faint hover:bg-danger-subtle hover:text-danger"
            >
              <Trash2 size={12} />
            </button>
          </div>
          {expandedId === t.id && t.supplier_id && <TaskSupplierPreview supplierId={t.supplier_id} />}
        </div>
      ))}
    </div>
  );
}
