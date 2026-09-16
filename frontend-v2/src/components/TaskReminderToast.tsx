import { Bell, Check, Clock, X } from 'lucide-react';
import { useState } from 'react';
import { formatCompanyName } from '../lib/format';
import { formatReminderDueLabel } from '../lib/taskSchedule';
import type { ReminderAlert } from '../lib/types';
import { Button } from './ui/Button';

const PRIORITY_LABEL: Record<ReminderAlert['priority'], string> = { high: 'Высокий', normal: 'Обычный', low: 'Низкий' };

const SNOOZE_PRESETS: { label: string; minutes: number }[] = [
  { label: '+5 мин', minutes: 5 },
  { label: '+15 мин', minutes: 15 },
  { label: '+30 мин', minutes: 30 },
  { label: '+1 час', minutes: 60 },
];

/** The persistent reminder card rendered inside a react-toastify toast and
 * reused, unstyled-container, inside the Notification Center list. Closing
 * via the surrounding toast's own X must call `onDismiss` (never silently
 * disappear) -- wired by the caller via react-toastify's `closeButton`. */
export function TaskReminderToast({
  reminder,
  onComplete,
  onSnooze,
  onOpen,
  busy = false,
  error,
}: {
  reminder: ReminderAlert;
  onComplete: () => void;
  onSnooze: (input: { minutes?: number; until?: string; timezone?: string }) => void;
  onOpen: () => void;
  busy?: boolean;
  error?: string | null;
}) {
  const [snoozeOpen, setSnoozeOpen] = useState(false);
  const [customDate, setCustomDate] = useState('');
  const [customTime, setCustomTime] = useState('');

  function snoozeTomorrow() {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    const local = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}T09:00`;
    onSnooze({ until: local, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' });
    setSnoozeOpen(false);
  }

  function snoozeCustom() {
    if (!customDate || !customTime) return;
    onSnooze({ until: `${customDate}T${customTime}`, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' });
    setSnoozeOpen(false);
  }

  return (
    <div className="w-[300px] rounded-lg border border-border-strong bg-surface p-3 shadow-lg" role="alert">
      <div className="mb-1.5 flex items-center gap-1.5 text-[12px] font-semibold text-accent">
        <Bell size={13} /> Время выполнить задачу
      </div>
      <p className="truncate text-[13px] font-medium text-ink">{reminder.title}</p>
      {reminder.supplier_name && <p className="truncate text-[11.5px] text-ink-muted">{formatCompanyName(reminder.supplier_name)}</p>}
      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-ink-faint">
        {reminder.request_name && <span className="truncate">Заявка «{reminder.request_name}»</span>}
        <span className="font-medium text-danger">{formatReminderDueLabel(reminder.scheduled_at)}</span>
        {reminder.priority !== 'normal' && <span>Приоритет: {PRIORITY_LABEL[reminder.priority]}</span>}
      </div>

      {error && <p className="mt-1.5 text-[11px] text-danger">{error}</p>}

      {!snoozeOpen ? (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <Button size="sm" variant="primary" disabled={busy} icon={<Check size={12} />} onClick={onComplete} aria-label="Отметить задачу выполненной">Выполнено</Button>
          <Button size="sm" variant="secondary" disabled={busy} icon={<Clock size={12} />} onClick={() => setSnoozeOpen(true)} aria-label="Отложить напоминание">Отложить</Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={onOpen} aria-label="Открыть связанную задачу">Открыть</Button>
        </div>
      ) : (
        <div className="mt-2.5 flex flex-col gap-1.5">
          <div className="flex flex-wrap gap-1">
            {SNOOZE_PRESETS.map((preset) => (
              <button key={preset.minutes} type="button" disabled={busy} onClick={() => { onSnooze({ minutes: preset.minutes }); setSnoozeOpen(false); }} className="h-7 rounded-md border border-border-strong px-2 text-[11px] font-medium text-ink hover:bg-surface-hover disabled:opacity-50">{preset.label}</button>
            ))}
            <button type="button" disabled={busy} onClick={snoozeTomorrow} className="h-7 rounded-md border border-border-strong px-2 text-[11px] font-medium text-ink hover:bg-surface-hover disabled:opacity-50">Завтра</button>
          </div>
          <div className="flex items-center gap-1">
            <input aria-label="Дата отложенного напоминания" type="date" value={customDate} onChange={(e) => setCustomDate(e.target.value)} className="h-7 min-w-0 flex-1 rounded-md border border-border-strong bg-canvas px-1.5 text-[11px] text-ink outline-none focus:border-accent" />
            <input aria-label="Время отложенного напоминания" type="time" value={customTime} onChange={(e) => setCustomTime(e.target.value)} className="h-7 w-[84px] rounded-md border border-border-strong bg-canvas px-1.5 text-[11px] text-ink outline-none focus:border-accent" />
            <button type="button" disabled={busy || !customDate || !customTime} onClick={snoozeCustom} className="h-7 rounded-md bg-accent px-2 text-[11px] font-medium text-white disabled:opacity-40">ОК</button>
          </div>
          <button type="button" onClick={() => setSnoozeOpen(false)} aria-label="Назад" className="self-start text-[11px] text-ink-faint hover:text-ink">Назад</button>
        </div>
      )}
    </div>
  );
}

export function ReminderOverflowToast({ count, onOpenCenter }: { count: number; onOpenCenter: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpenCenter}
      className="flex w-[300px] items-center gap-2 rounded-lg border border-border-strong bg-surface p-3 text-left shadow-lg hover:bg-surface-hover"
    >
      <Bell size={15} className="shrink-0 text-accent" />
      <span className="text-[12.5px] font-medium text-ink">Ещё {count} {count === 1 ? 'задача требует' : 'задач требуют'} внимания</span>
    </button>
  );
}

export function ReminderToastCloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-label="Скрыть уведомление" className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-ink-faint hover:bg-surface-hover hover:text-ink">
      <X size={13} />
    </button>
  );
}
