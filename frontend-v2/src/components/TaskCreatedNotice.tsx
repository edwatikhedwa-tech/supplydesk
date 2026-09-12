import { Check, RotateCcw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { formatTaskDeadline } from '../lib/taskSchedule';

export interface CreatedTaskNotice {
  id: number;
  title: string;
  dueDate: string | null;
  dueAt?: string | null;
  timezone?: string | null;
}

/**
 * A short-lived, recoverable confirmation for a task that has just been
 * created. It deliberately names the saved task and its actual date-only
 * deadline: the current task model has no time field, so this component never
 * fabricates a time or reminder.
 */
export function TaskCreatedNotice({
  task,
  onOpen,
  onUndo,
  onDismiss,
}: {
  task: CreatedTaskNotice;
  onOpen: () => void;
  onUndo: () => Promise<void>;
  onDismiss: () => void;
}) {
  const [undoing, setUndoing] = useState(false);
  const [undoError, setUndoError] = useState('');

  useEffect(() => {
    const timer = window.setTimeout(onDismiss, 10_000);
    return () => window.clearTimeout(timer);
  }, [onDismiss, task.id]);

  async function handleUndo() {
    setUndoing(true);
    setUndoError('');
    try {
      await onUndo();
      onDismiss();
    } catch {
      setUndoError('Не удалось отменить создание. Задача сохранена — попробуйте удалить её из списка.');
    } finally {
      setUndoing(false);
    }
  }

  return (
    <div role="status" className="fixed bottom-4 left-4 right-4 z-50 flex max-w-lg flex-wrap items-center gap-x-3 gap-y-1.5 rounded-md border border-success-border bg-success-subtle px-3 py-2 text-[12px] text-ink shadow-lg sm:left-auto">
      <span className="flex min-w-0 items-center gap-1.5">
        <Check size={14} className="shrink-0 text-success" aria-hidden="true" />
        <span className="truncate">Задача «{task.title}» добавлена · {formatTaskDeadline({ due_date: task.dueDate, due_at: task.dueAt ?? null, timezone: task.timezone ?? null })}</span>
      </span>
      <span className="flex items-center gap-2">
        <button type="button" onClick={onOpen} className="font-medium text-accent hover:text-accent-hover">
          Открыть
        </button>
        <button type="button" disabled={undoing} onClick={() => void handleUndo()} className="inline-flex items-center gap-1 font-medium text-ink-muted hover:text-ink disabled:opacity-60">
          <RotateCcw size={12} aria-hidden="true" />
          {undoing ? 'Отменяем…' : 'Отменить'}
        </button>
      </span>
      {undoError && <p className="basis-full text-[11.5px] text-danger">{undoError}</p>}
    </div>
  );
}
