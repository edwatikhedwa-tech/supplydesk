import { ListTodo } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { dueAtInput } from '../lib/taskSchedule';
import { Button } from './ui/Button';
import { DatePicker } from './ui/DatePicker';
import { TaskCreatedNotice, type CreatedTaskNotice } from './TaskCreatedNotice';

/** Small "+ Задача" affordance for detail pages -- creates a task already
 * linked to this request/supplier, per the concept doc's "задачи могут
 * быть связаны с заявкой/поставщиком". Viewing/managing tasks stays on the
 * Dashboard; this is create-only, on purpose, to keep detail pages focused. */
export function QuickAddTaskButton({ requestId, supplierId }: { requestId?: number; supplierId?: number }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [dueTime, setDueTime] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [createdTask, setCreatedTask] = useState<CreatedTaskNotice | null>(null);
  const [createError, setCreateError] = useState('');

  async function submit() {
    if (!title.trim()) return;
    setSubmitting(true);
    setCreateError('');
    try {
      const schedule = dueAtInput(dueDate, dueTime);
      const created = await api.createTask({ title: title.trim(), due_date: dueDate || undefined, due_at: schedule.due_at ?? undefined, timezone: schedule.timezone ?? undefined, request_id: requestId, supplier_id: supplierId });
      setCreatedTask({ id: created.task_id, title: title.trim(), dueDate: dueDate || null, dueAt: schedule.due_at, timezone: schedule.timezone });
      setTitle('');
      setDueDate('');
      setDueTime('');
      setOpen(false);
    } catch {
      setCreateError('Не удалось создать задачу. Проверьте соединение и повторите попытку.');
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) {
    return (
      <>
        <Button variant="secondary" size="sm" icon={<ListTodo size={13} />} onClick={() => setOpen(true)}>
          Задача
        </Button>
        {createdTask && (
          <TaskCreatedNotice
            task={createdTask}
            onOpen={() => navigate(`/?task=${createdTask.id}`)}
            onUndo={async () => {
              await api.deleteTask(createdTask.id);
            }}
            onDismiss={() => setCreatedTask(null)}
          />
        )}
      </>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <input
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && void submit()}
        placeholder="Текст задачи…"
        className="h-8 w-[220px] rounded-md border border-border-strong bg-surface px-2.5 text-[12.5px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
      />
      <DatePicker value={dueDate} onChange={setDueDate} className="w-[150px]" />
      <input aria-label="Время задачи" type="time" value={dueTime} onChange={(e) => setDueTime(e.target.value)} className="h-8 rounded-md border border-border-strong bg-surface px-2 text-[12.5px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border" />
      <Button variant="primary" size="sm" disabled={!title.trim() || submitting} onClick={() => void submit()}>
        Добавить
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
        Отмена
      </Button>
      {createError && <p className="basis-full text-[11.5px] text-danger">{createError}</p>}
    </div>
  );
}
