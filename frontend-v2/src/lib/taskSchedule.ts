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
