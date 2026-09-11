import clsx from 'clsx';
import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

export type Tone = 'neutral' | 'accent' | 'info' | 'warning' | 'success' | 'danger';
export type BadgeVariant = 'subtle' | 'outline';

const toneClasses: Record<Tone, string> = {
  neutral: 'bg-surface-hover text-ink-soft border-border-strong',
  accent: 'bg-accent-subtle text-accent border-accent-border',
  info: 'bg-info-subtle text-info border-info-border',
  warning: 'bg-warning-subtle text-warning border-warning-border',
  success: 'bg-success-subtle text-success border-success-border',
  danger: 'bg-danger-subtle text-danger border-danger-border',
};

// No fill, just a colored border + colored text -- e.g. ReUI's "*-outline"
// badge variants (see ConversationStatusSelect, built to match
// @reui/c-select-19's reference look without its paywalled Badge/Select).
const outlineToneClasses: Record<Tone, string> = {
  neutral: 'bg-transparent text-ink-muted border-border-strong',
  accent: 'bg-transparent text-accent border-accent-border',
  info: 'bg-transparent text-info border-info-border',
  warning: 'bg-transparent text-warning border-warning-border',
  success: 'bg-transparent text-success border-success-border',
  danger: 'bg-transparent text-danger border-danger-border',
};

export function Badge({
  tone = 'neutral',
  variant = 'subtle',
  children,
  dot = false,
  className,
}: {
  tone?: Tone;
  variant?: BadgeVariant;
  children: ReactNode;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-none whitespace-nowrap',
        variant === 'outline' ? outlineToneClasses[tone] : toneClasses[tone],
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
