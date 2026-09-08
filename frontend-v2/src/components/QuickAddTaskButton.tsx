import { Check, ListTodo } from 'lucide-react';
import { useState } from 'react';
import { api } from '../lib/api';
import { Button } from './ui/Button';
import { DatePicker } from './ui/DatePicker';

/** Small "+ Задача" affordance for detail pages -- creates a task already
 * linked to this request/supplier, per the concept doc's "задачи могут
 * быть связаны с заявкой/поставщиком". Viewing/managing tasks stays on the
 * Dashboard; this is create-only, on purpose, to keep detail pages focused. */
export function QuickAddTaskButton({ requestId, supplierId }: { requestId?: number; supplierId?: number }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function submit() {
    if (!title.trim()) return;
    setSubmitting(true);
    try {
      await api.createTask({ title: title.trim(), due_date: dueDate || undefined, request_id: requestId, supplier_id: supplierId });
      setTitle('');
      setDueDate('');
      setOpen(false);
      setDone(true);
      setTimeout(() => setDone(false), 2000);
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <Button variant="secondary" size="sm" icon={<Check size={13} />} disabled>
        Задача добавлена
      </Button>
    );
  }

  if (!open) {
    return (
      <Button variant="secondary" size="sm" icon={<ListTodo size={13} />} onClick={() => setOpen(true)}>
        Задача
      </Button>
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
      <Button variant="primary" size="sm" disabled={!title.trim() || submitting} onClick={() => void submit()}>
        Добавить
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
        Отмена
      </Button>
    </div>
  );
}
