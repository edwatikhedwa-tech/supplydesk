import { Bell, Check, ListTodo, Pencil, Plus, Trash2, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { formatCompanyName } from '../lib/format';
import { dueAtInput, formatTaskDeadline, formatTaskReminder } from '../lib/taskSchedule';
import type { Task, TaskReminderInput } from '../lib/types';
import { useApiData } from '../lib/useApiData';
import { Button } from './ui/Button';
import { DatePicker } from './ui/DatePicker';
import { EmptyState } from './ui/EmptyState';
import { ErrorState, LoadingState } from './ui/ErrorState';
import { TaskSupplierPreview } from './TaskSupplierPreview';
import { TaskCreatedNotice, type CreatedTaskNotice } from './TaskCreatedNotice';

/** Dashboard's "Мои задачи" block (§2, §12 of the concept doc) -- a
 * deliberately separate entity from the system-detected "Требует внимания"
 * cards above it: those are events SupplyDesk noticed on its own, tasks are
 * things the owner decided to do. */
export function TasksSection() {
  const state = useApiData(() => api.listTasks().then((r) => r.items), []);
  const [searchParams] = useSearchParams();
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [dueTime, setDueTime] = useState('');
  const [reminderChannel, setReminderChannel] = useState<'' | TaskReminderInput['channel']>('');
  const [reminderPhone, setReminderPhone] = useState('');
  const [phoneReminderMode, setPhoneReminderMode] = useState<'mock' | 'disabled'>('disabled');
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [createdTask, setCreatedTask] = useState<CreatedTaskNotice | null>(null);
  const [createError, setCreateError] = useState('');
  const requestedTaskId = Number(searchParams.get('task'));
  const readyTasks = state.status === 'ready' ? state.data : null;

  useEffect(() => {
    void api.listTasks().then((result) => setPhoneReminderMode(result.phone_reminders_mode)).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (
      readyTasks &&
      Number.isInteger(requestedTaskId) &&
      requestedTaskId > 0 &&
      readyTasks.some((task) => task.id === requestedTaskId)
    ) {
      setExpandedId(requestedTaskId);
      window.requestAnimationFrame(() => document.getElementById(`task-${requestedTaskId}`)?.scrollIntoView({ block: 'center' }));
    }
  }, [requestedTaskId, readyTasks]);

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
    setCreateError('');
    try {
      const schedule = dueAtInput(dueDate, dueTime);
      if (reminderChannel && (!schedule.due_at || !schedule.timezone)) {
        setCreateError('Для напоминания укажите дату и время задачи.');
        return;
      }
      if (reminderChannel === 'phone' && reminderPhone.replace(/\D/g, '').length < 7) {
        setCreateError('Для телефонного mock укажите номер.');
        return;
      }
      const created = await api.createTask({
        title: title.trim(), due_date: dueDate || undefined, due_at: schedule.due_at ?? undefined, timezone: schedule.timezone ?? undefined,
        reminders: reminderChannel && schedule.due_at && schedule.timezone ? [{ channel: reminderChannel, scheduled_at: schedule.due_at, timezone: schedule.timezone, recipient: reminderChannel === 'phone' ? reminderPhone : undefined }] : undefined,
      });
      setCreatedTask({ id: created.task_id, title: title.trim(), dueDate: dueDate || null, dueAt: schedule.due_at, timezone: schedule.timezone });
      setTitle('');
      setDueDate('');
      setDueTime('');
      setReminderChannel('');
      setReminderPhone('');
      setAdding(false);
      state.reload();
    } catch {
      // Keep the form and its text intact so the task can be retried safely.
      setCreateError('Не удалось создать задачу. Проверьте соединение и повторите попытку.');
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

      {adding && (
        <div className="flex flex-wrap items-center gap-1.5 border-b border-border px-4 py-2.5">
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void addTask()}
            placeholder="Например: позвонить поставщику завтра в 11:00"
            className="h-8 min-w-0 basis-full flex-1 rounded-md border border-border-strong bg-canvas px-2.5 text-[12.5px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border lg:basis-auto"
          />
          <DatePicker value={dueDate} onChange={setDueDate} className="w-full md:w-[160px]" />
          <input aria-label="Время задачи" type="time" value={dueTime} onChange={(e) => setDueTime(e.target.value)} className="h-8 rounded-md border border-border-strong bg-canvas px-2 text-[12.5px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border" />
          <select aria-label="Напоминание при создании задачи" value={reminderChannel} onChange={(event) => setReminderChannel(event.target.value as '' | TaskReminderInput['channel'])} className="h-8 rounded-md border border-border-strong bg-canvas px-2 text-[12px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border">
            <option value="">Без напоминания</option><option value="in_app">In-app</option><option value="email">Email</option><option value="phone" disabled={phoneReminderMode !== 'mock'}>{phoneReminderMode === 'mock' ? 'Позвонить мне · mock' : 'Позвонить мне · скоро'}</option>
          </select>
          {reminderChannel === 'phone' && <input aria-label="Номер для телефонного mock" value={reminderPhone} onChange={(event) => setReminderPhone(event.target.value)} placeholder="Номер для mock" inputMode="tel" className="h-8 min-w-0 rounded-md border border-border-strong bg-canvas px-2 text-[12px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border" />}
          <Button variant="primary" size="sm" disabled={!title.trim() || submitting} onClick={() => void addTask()}>
            Добавить
          </Button>
          <button type="button" onClick={() => setAdding(false)} aria-label="Отменить создание задачи" className="flex h-8 w-8 items-center justify-center rounded-md text-ink-faint hover:bg-surface-hover">
            <X size={14} />
          </button>
          {createError && <p className="basis-full text-[11.5px] text-danger">{createError}</p>}
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
              editingId={editingId}
              onExpand={setExpandedId}
              onEdit={setEditingId}
              onReload={state.reload}
              onToggle={toggleDone}
              onDelete={remove}
              phoneReminderMode={phoneReminderMode}
            />
          )}
          {groups.today.length > 0 && (
            <TaskGroup
              label="Сегодня"
              tone="text-warning"
              tasks={groups.today}
              busyId={busyId}
              expandedId={expandedId}
              editingId={editingId}
              onExpand={setExpandedId}
              onEdit={setEditingId}
              onReload={state.reload}
              onToggle={toggleDone}
              onDelete={remove}
              phoneReminderMode={phoneReminderMode}
            />
          )}
          {groups.upcoming.length > 0 && (
            <TaskGroup
              label="Скоро"
              tone="text-ink-muted"
              tasks={groups.upcoming}
              busyId={busyId}
              expandedId={expandedId}
              editingId={editingId}
              onExpand={setExpandedId}
              onEdit={setEditingId}
              onReload={state.reload}
              onToggle={toggleDone}
              onDelete={remove}
              phoneReminderMode={phoneReminderMode}
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
  editingId,
  onExpand,
  onEdit,
  onReload,
  onToggle,
  onDelete,
  phoneReminderMode,
}: {
  label: string;
  tone: string;
  tasks: Task[];
  busyId: number | null;
  expandedId: number | null;
  editingId: number | null;
  onExpand: (id: number | null) => void;
  onEdit: (id: number | null) => void;
  onReload: () => void;
  onToggle: (id: number, done: boolean) => void;
  onDelete: (id: number) => void;
  phoneReminderMode: 'mock' | 'disabled';
}) {
  return (
    <div>
      <p className={`px-4 pt-2.5 text-[10.5px] font-semibold uppercase tracking-wide ${tone}`}>{label}</p>
      {tasks.map((t) => (
        <div id={`task-${t.id}`} key={t.id} className="border-b border-border px-4 py-2 last:border-0 hover:bg-surface-hover">
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
              {t.reminders.length > 0 && <p className="mt-0.5 flex items-center gap-1 truncate text-[10.5px] text-ink-faint"><Bell size={10} className="shrink-0" />{formatTaskReminder(t.reminders[0])}{t.reminders.length > 1 ? ` · ещё ${t.reminders.length - 1}` : ''}</p>}
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
            {t.due_date && <span className="shrink-0 text-[11px] text-ink-faint max-[500px]:hidden">{formatTaskDeadline(t)}</span>}
            <button
              type="button"
              onClick={() => onEdit(editingId === t.id ? null : t.id)}
              aria-label="Редактировать задачу"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-ink-faint hover:bg-surface-hover hover:text-ink"
            >
              <Pencil size={12} />
            </button>
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
          {editingId === t.id && <TaskDetailsEditor task={t} phoneReminderMode={phoneReminderMode} onCancel={() => onEdit(null)} onSaved={() => { onEdit(null); onReload(); }} />}
          {expandedId === t.id && t.supplier_id && <TaskSupplierPreview supplierId={t.supplier_id} />}
        </div>
      ))}
    </div>
  );
}

function TaskDetailsEditor({ task, phoneReminderMode, onCancel, onSaved }: { task: Task; phoneReminderMode: 'mock' | 'disabled'; onCancel: () => void; onSaved: () => void }) {
  const members = useApiData(() => api.listWorkspaceMembers().then((result) => result.items), []);
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description);
  const [dueDate, setDueDate] = useState(task.due_date ?? '');
  const [dueTime, setDueTime] = useState(task.due_at?.slice(11, 16) ?? '');
  const [priority, setPriority] = useState<Task['priority']>(task.priority);
  const [assigneeId, setAssigneeId] = useState(task.assignee_user_id ? String(task.assignee_user_id) : '');
  const [reminders, setReminders] = useState<TaskReminderInput[]>(() => task.reminders.map((reminder) => ({
    channel: reminder.channel, scheduled_at: reminder.scheduled_at, timezone: reminder.timezone, recipient: reminder.recipient ?? undefined,
  })));
  const [reminderChannel, setReminderChannel] = useState<TaskReminderInput['channel']>('in_app');
  const [reminderDate, setReminderDate] = useState(task.due_date ?? '');
  const [reminderTime, setReminderTime] = useState(task.due_at?.slice(11, 16) ?? '');
  const [reminderPhone, setReminderPhone] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    if (!title.trim()) return;
    setSaving(true);
    setError('');
    try {
      const schedule = dueAtInput(dueDate, dueTime);
      await api.updateTask(task.id, {
        title: title.trim(), description, due_date: dueDate || undefined,
        due_at: schedule.due_at ?? undefined, timezone: schedule.timezone ?? undefined,
        priority, assignee_user_id: assigneeId ? Number(assigneeId) : undefined,
        reminders,
      });
      onSaved();
    } catch {
      setError('Не удалось сохранить задачу. Проверьте данные и повторите попытку.');
    } finally {
      setSaving(false);
    }
  }

  function addReminder() {
    const schedule = dueAtInput(reminderDate, reminderTime);
    if (!schedule.due_at || !schedule.timezone) return;
    if (reminderChannel === 'phone' && reminderPhone.replace(/\D/g, '').length < 7) {
      setError('Для телефонного mock укажите номер.');
      return;
    }
    setError('');
    setReminders((items) => [...items, { channel: reminderChannel, scheduled_at: schedule.due_at!, timezone: schedule.timezone!, recipient: reminderChannel === 'phone' ? reminderPhone : undefined }]);
    setReminderPhone('');
  }

  return (
    <div className="mt-2 grid gap-2 rounded-md border border-border-strong bg-canvas p-2.5 sm:grid-cols-2">
      <input value={title} onChange={(event) => setTitle(event.target.value)} aria-label="Название задачи" className="h-8 rounded-md border border-border-strong bg-surface px-2.5 text-[12.5px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border sm:col-span-2" />
      <textarea value={description} onChange={(event) => setDescription(event.target.value)} aria-label="Описание задачи" placeholder="Описание задачи…" rows={2} className="resize-y rounded-md border border-border-strong bg-surface px-2.5 py-2 text-[12.5px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border sm:col-span-2" />
      <DatePicker value={dueDate} onChange={setDueDate} />
      <input aria-label="Время задачи" type="time" value={dueTime} onChange={(event) => setDueTime(event.target.value)} className="h-8 rounded-md border border-border-strong bg-surface px-2 text-[12.5px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border" />
      <select aria-label="Приоритет задачи" value={priority} onChange={(event) => setPriority(event.target.value as Task['priority'])} className="h-8 rounded-md border border-border-strong bg-surface px-2 text-[12.5px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border">
        <option value="low">Низкий приоритет</option><option value="normal">Обычный приоритет</option><option value="high">Высокий приоритет</option>
      </select>
      <select aria-label="Исполнитель задачи" value={assigneeId} onChange={(event) => setAssigneeId(event.target.value)} disabled={members.status !== 'ready'} className="h-8 rounded-md border border-border-strong bg-surface px-2 text-[12.5px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border disabled:opacity-60">
        {!assigneeId && <option value="">Автор задачи</option>}
        {members.status === 'ready' && members.data.map((member) => <option key={member.id} value={member.id}>{member.display_name}{member.role === 'owner' ? ' · владелец' : ''}</option>)}
      </select>
      <section className="rounded-md border border-border bg-surface p-2 sm:col-span-2" aria-label="Напоминания задачи">
        <div className="mb-2 flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5 text-[12px] font-medium text-ink"><Bell size={13} className="text-ink-muted" /> Напоминания</div>
          <span className="text-right text-[10.5px] text-ink-faint">Доставка пока не запускается</span>
        </div>
        {reminders.length > 0 && <div className="mb-2 flex flex-col gap-1">
          {reminders.map((reminder, index) => <div key={`${reminder.channel}-${reminder.scheduled_at}-${index}`} className="flex items-center gap-2 rounded-md bg-canvas px-2 py-1.5 text-[11.5px] text-ink-soft">
            <span className="min-w-0 flex-1 truncate">{reminder.channel === 'email' ? 'Email' : reminder.channel === 'phone' ? 'Позвонить мне · mock' : 'In-app'} · {reminder.scheduled_at.replace('T', ' ')} ({reminder.timezone})</span>
            <button type="button" onClick={() => setReminders((items) => items.filter((_, itemIndex) => itemIndex !== index))} aria-label="Удалить напоминание" className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-ink-faint hover:bg-danger-subtle hover:text-danger"><Trash2 size={12} /></button>
          </div>)}
        </div>}
        <div className="grid gap-1.5 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
          <select aria-label="Канал напоминания" value={reminderChannel} onChange={(event) => setReminderChannel(event.target.value as TaskReminderInput['channel'])} className="h-8 rounded-md border border-border-strong bg-surface px-2 text-[12px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"><option value="in_app">In-app</option><option value="email">Email</option><option value="phone" disabled={phoneReminderMode !== 'mock'}>{phoneReminderMode === 'mock' ? 'Позвонить мне · mock' : 'Позвонить мне · скоро'}</option></select>
          {reminderChannel === 'phone' && <input aria-label="Номер для телефонного mock" value={reminderPhone} onChange={(event) => setReminderPhone(event.target.value)} placeholder="Номер для mock" inputMode="tel" className="h-8 min-w-0 rounded-md border border-border-strong bg-surface px-2 text-[12px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border" />}
          <DatePicker value={reminderDate} onChange={setReminderDate} placeholder="Дата напоминания" />
          <input aria-label="Время напоминания" type="time" value={reminderTime} onChange={(event) => setReminderTime(event.target.value)} className="h-8 rounded-md border border-border-strong bg-surface px-2 text-[12px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border" />
          <button type="button" onClick={addReminder} disabled={!reminderDate || !reminderTime || reminders.length >= 5} className="h-8 rounded-md border border-border-strong px-2.5 text-[12px] font-medium text-ink-muted hover:bg-surface-hover hover:text-ink disabled:opacity-50">Добавить</button>
        </div>
        <p className="mt-1.5 text-[10.5px] text-ink-faint">Email использует адрес вашего профиля. {phoneReminderMode === 'mock' ? 'Телефонный канал работает только как local mock: звонка не будет.' : 'Телефонные напоминания скоро будут доступны.'}</p>
      </section>
      <div className="flex items-center justify-end gap-2 sm:col-span-2">
        <button type="button" onClick={onCancel} className="h-8 rounded-md px-2.5 text-[12px] text-ink-muted hover:bg-surface-hover">Отмена</button>
        <button type="button" onClick={() => void save()} disabled={!title.trim() || saving} className="h-8 rounded-md bg-accent px-3 text-[12px] font-medium text-white hover:bg-accent-hover disabled:opacity-60">{saving ? 'Сохраняем…' : 'Сохранить'}</button>
      </div>
      {error && <p className="text-[11.5px] text-danger sm:col-span-2">{error}</p>}
    </div>
  );
}
