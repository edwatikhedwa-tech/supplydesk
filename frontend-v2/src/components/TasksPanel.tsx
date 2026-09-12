import { Plus, SquareCheck, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { api } from '../lib/api';
import { dueAtInput, formatTaskDeadline } from '../lib/taskSchedule';
import { useApiData } from '../lib/useApiData';
import { DatePicker } from './ui/DatePicker';
import { TaskSupplierPreview } from './TaskSupplierPreview';
import { TaskCreatedNotice, type CreatedTaskNotice } from './TaskCreatedNotice';

/** Right-rail task list scoped to this exact thread (request + supplier) --
 * the Dashboard's "Мои задачи" stays the place to see everything at once;
 * this is a quick in-context add/check-off without leaving the conversation. */
export function TasksPanel({
  requestId,
  supplierId,
  onClose,
}: {
  requestId: number;
  /** The global картотека id -- null until this thread's supplier is
   * confirmed/linked, since tasks.supplier_id references global_suppliers,
   * not the request-scoped suppliers row the thread itself points at. */
  supplierId: number | null;
  onClose: () => void;
}) {
  const state = useApiData(() => api.listTasks().then((r) => r.items), []);
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [dueTime, setDueTime] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [createdTask, setCreatedTask] = useState<CreatedTaskNotice | null>(null);
  const [createError, setCreateError] = useState('');

  const tasks =
    state.status === 'ready' && supplierId !== null
      ? state.data.filter((t) => t.request_id === requestId && t.supplier_id === supplierId)
      : [];

  async function addTask() {
    if (!title.trim() || supplierId === null) return;
    setSubmitting(true);
    setCreateError('');
    try {
      const schedule = dueAtInput(dueDate, dueTime);
      const created = await api.createTask({ title: title.trim(), due_date: dueDate || undefined, due_at: schedule.due_at ?? undefined, timezone: schedule.timezone ?? undefined, request_id: requestId, supplier_id: supplierId });
      setCreatedTask({ id: created.task_id, title: title.trim(), dueDate: dueDate || null, dueAt: schedule.due_at, timezone: schedule.timezone });
      setTitle('');
      setDueDate('');
      setDueTime('');
      setAdding(false);
      state.reload();
    } catch {
      setCreateError('Не удалось создать задачу. Проверьте соединение и повторите попытку.');
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleDone(taskId: number) {
    setBusyId(taskId);
    try {
      await api.setTaskDone(taskId, true);
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
    <div className="flex h-full w-full shrink-0 flex-col border-l border-border bg-surface sm:w-72">
      {createdTask && (
        <TaskCreatedNotice
          task={createdTask}
          onOpen={() => {
            setExpandedId(createdTask.id);
            setCreatedTask(null);
          }}
          onUndo={async () => {
            await api.deleteTask(createdTask.id);
            state.reload();
          }}
          onDismiss={() => setCreatedTask(null)}
        />
      )}
      <div className="flex items-center justify-between border-b border-border px-3.5 py-2.5">
        <span className="flex items-center gap-1.5 text-[12.5px] font-semibold text-ink">
          <SquareCheck size={14} />
          Задачи
        </span>
        <button type="button" onClick={onClose} aria-label="Закрыть задачи" className="flex h-6 w-6 items-center justify-center rounded-md text-ink-muted hover:bg-surface-hover hover:text-ink">
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {supplierId === null ? (
          <p className="text-[12px] text-ink-faint">
            Карточка этого поставщика ещё не подтверждена (нет проверенного ИНН) — задачу пока нельзя привязать. Можно добавить общую
            задачу по заявке на Дашборде.
          </p>
        ) : (
          <>
            {state.status === 'loading' && <p className="text-[12px] text-ink-faint">Загружаем…</p>}
            {state.status === 'ready' && tasks.length === 0 && !adding && (
              <p className="text-[12px] text-ink-faint">Задач по этому поставщику пока нет.</p>
            )}
          </>
        )}
        <div className="flex flex-col gap-1.5">
          {tasks.map((t) => (
            <div key={t.id} className="rounded-md border border-border px-2.5 py-2">
              <div className="flex items-start gap-2">
                <button
                  type="button"
                  disabled={busyId === t.id}
                  onClick={() => void toggleDone(t.id)}
                  aria-label="Отметить выполненной"
                  className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-border-strong text-transparent hover:border-accent hover:text-accent"
                >
                  <SquareCheck size={11} />
                </button>
                <button
                  type="button"
                  disabled={!t.supplier_id}
                  onClick={() => setExpandedId((prev) => (prev === t.id ? null : t.id))}
                  className="min-w-0 flex-1 text-left disabled:cursor-default"
                >
                  <p className="text-[12.5px] leading-snug text-ink">{t.title}</p>
                  {t.due_date && <p className="mt-0.5 text-[11px] text-ink-faint">{formatTaskDeadline(t)}</p>}
                </button>
                <button
                  type="button"
                  disabled={busyId === t.id}
                  onClick={() => void remove(t.id)}
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

        {adding && (
          <div className="mt-2 flex flex-col gap-1.5 rounded-md border border-border-strong bg-canvas p-2">
            <input
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void addTask()}
              placeholder="Текст задачи…"
              className="h-7 w-full rounded-md border border-border-strong bg-surface px-2 text-[12px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
            <DatePicker value={dueDate} onChange={setDueDate} size="sm" />
            <input aria-label="Время задачи" type="time" value={dueTime} onChange={(e) => setDueTime(e.target.value)} className="h-7 rounded-md border border-border-strong bg-surface px-2 text-[12px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border" />
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={!title.trim() || submitting}
                onClick={() => void addTask()}
                className="h-7 flex-1 rounded-md bg-accent text-[12px] font-medium text-white hover:bg-accent-hover disabled:opacity-40"
              >
                Добавить
              </button>
              <button type="button" onClick={() => setAdding(false)} className="h-7 rounded-md px-2 text-[12px] text-ink-muted hover:bg-surface-hover">
                Отмена
              </button>
            </div>
            {createError && <p className="text-[11.5px] text-danger">{createError}</p>}
          </div>
        )}
      </div>

      {!adding && supplierId !== null && (
        <div className="border-t border-border p-2.5">
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="flex h-8 w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-border-strong text-[12px] text-ink-muted hover:border-accent hover:text-accent"
          >
            <Plus size={13} /> Добавить задачу
          </button>
        </div>
      )}
    </div>
  );
}
