export const TODAY = new Date('2026-09-05T09:00:00+03:00');

const DAY_MS = 24 * 60 * 60 * 1000;

export function daysFromToday(iso: string | null): number | null {
  if (!iso) return null;
  const d = new Date(iso + 'T00:00:00+03:00');
  return Math.round((d.getTime() - TODAY.getTime()) / DAY_MS);
}

export type DeadlineUrgency = 'overdue' | 'today' | 'soon' | 'normal' | 'none';

export function deadlineUrgency(iso: string | null): DeadlineUrgency {
  const days = daysFromToday(iso);
  if (days === null) return 'none';
  if (days < 0) return 'overdue';
  if (days === 0) return 'today';
  if (days <= 3) return 'soon';
  return 'normal';
}

export function formatDeadline(iso: string | null): string {
  if (!iso) return 'Без срока';
  const days = daysFromToday(iso);
  const date = new Date(iso + 'T00:00:00+03:00');
  const formatted = date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
  if (days === 0) return `Сегодня, ${formatted}`;
  if (days === 1) return `Завтра, ${formatted}`;
  if (days !== null && days < 0) return `Просрочено на ${Math.abs(days)} дн · ${formatted}`;
  return formatted;
}

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso);
  const diffMs = TODAY.getTime() - then.getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return 'только что';
  if (diffMin < 60) return `${diffMin} мин назад`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr} ч назад`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay === 1) return 'вчера';
  if (diffDay < 7) return `${diffDay} дн назад`;
  return then.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatPercent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

export function initials(name: string): string {
  const parts = name.replace(/[«»"]/g, '').split(/\s+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? '');
  return letters.join('') || '?';
}
