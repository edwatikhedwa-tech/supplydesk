import { formatDeadline } from './format';
import type { Task, TaskReminder } from './types';

export function dueAtInput(date: string, time: string): Pick<Task, 'due_at' | 'timezone'> {
  if (!date || !time) return { due_at: null, timezone: null };
  return {
    due_at: `${date}T${time}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  };
}

export function formatTaskDeadline(task: Pick<Task, 'due_date' | 'due_at' | 'timezone'>): string {
  if (!task.due_at) return formatDeadline(task.due_date);
  const time = task.due_at.slice(11, 16);
  return `${formatDeadline(task.due_date)} · ${time}${task.timezone ? ` (${task.timezone})` : ''}`;
}

export function formatTaskReminder(reminder: Pick<TaskReminder, 'channel' | 'scheduled_at' | 'timezone'>): string {
  const channel = reminder.channel === 'email' ? 'Email' : reminder.channel === 'phone' ? 'Позвонить мне · mock' : 'In-app';
  return `${channel} · ${reminder.scheduled_at.replace('T', ' ')} (${reminder.timezone})`;
}

/** "Просрочено 15 мин" / "Просрочено 2 ч" / "Просрочено 1 день" / "Срок: сейчас".
 * `scheduledAt` is read as browser-local wall time, matching how it was
 * created (`Intl.DateTimeFormat().resolvedOptions().timeZone`) for the
 * common single-timezone user -- a disclosed simplification, not a full
 * per-reminder timezone conversion. */
export function formatReminderDueLabel(scheduledAt: string): string {
  const scheduled = new Date(scheduledAt.length === 16 ? `${scheduledAt}:00` : scheduledAt);
  const diffMs = Date.now() - scheduled.getTime();
  if (diffMs < 60_000) return 'Срок: сейчас';
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `Просрочено ${minutes} мин`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Просрочено ${hours} ч`;
  const days = Math.floor(hours / 24);
  return `Просрочено ${days} ${days === 1 ? 'день' : 'дн'}`;
}
