import clsx from 'clsx';
import type { ReactNode } from 'react';

export type Tone = 'neutral' | 'accent' | 'info' | 'warning' | 'success' | 'danger';

const toneClasses: Record<Tone, string> = {
  neutral: 'bg-surface-hover text-ink-soft border-border-strong',
  accent: 'bg-accent-subtle text-accent border-accent-border',
  info: 'bg-info-subtle text-info border-info-border',
  warning: 'bg-warning-subtle text-warning border-warning-border',
  success: 'bg-success-subtle text-success border-success-border',
  danger: 'bg-danger-subtle text-danger border-danger-border',
};

export function Badge({
  tone = 'neutral',
  children,
  dot = false,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-none whitespace-nowrap',
        toneClasses[tone],
        className,
      )}
    >
      {dot && <DotIcon tone={tone} />}
      {children}
    </span>
  );
}

const dotColor: Record<Tone, string> = {
  neutral: 'bg-ink-faint',
  accent: 'bg-accent',
  info: 'bg-info',
  warning: 'bg-warning',
  success: 'bg-success',
  danger: 'bg-danger',
};

export function DotIcon({ tone = 'neutral' }: { tone?: Tone }) {
  return <span className={clsx('h-1.5 w-1.5 shrink-0 rounded-full', dotColor[tone])} />;
}
