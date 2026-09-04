import { cn } from '@/lib/utils';

export type StatusBadgeTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

interface StatusBadgeProps {
  label: string;
  tone?: StatusBadgeTone;
  title?: string;
  dot?: boolean;
}
const toneClasses: Record<StatusBadgeTone, string> = {
  neutral: 'bg-ink-100 text-ink-600 ring-ink-200',
  info: 'bg-accent-50 text-accent-700 ring-accent-200',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  warning: 'bg-amber-50 text-amber-800 ring-amber-200',
  danger: 'bg-rose-50 text-rose-700 ring-rose-200',
};

const dotClasses: Record<StatusBadgeTone, string> = {
  neutral: 'bg-ink-400',
  info: 'bg-accent-500',
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  danger: 'bg-rose-500',
};

/** Status answers only “what is happening?”; counts and actions stay outside. */
export function StatusBadge({ label, tone = 'neutral', title, dot = false }: StatusBadgeProps) {
  return (
    <span title={title} className={cn('inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-2xs font-semibold ring-1 ring-inset', toneClasses[tone])}>
      {dot && <span aria-hidden="true" className={cn('h-1.5 w-1.5 rounded-full', dotClasses[tone])} />}
      {label}
    </span>
  );
}

/** Canonical semantic badge name for new screens; StatusBadge stays as the
 * compatibility export used by existing mail and supplier flows. */
export const Badge = StatusBadge;

export function Count({ value, label }: { value: number | string; label?: string }) {
  return <span aria-label={label} className="tabular-nums text-xs font-medium text-ink-400">{value}</span>;
}
