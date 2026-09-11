import type { HTMLAttributes } from 'react';
import { cn } from '../../lib/cn';

/**
 * Local, token-aware adaptation of ReUI's free C Frame 2 pattern.
 * It deliberately has no registry dependency: Messages already owns the
 * same Tailwind tokens and can use this composition without package changes.
 */
export function Frame({ className, children, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn('mx-auto flex w-full max-w-4xl flex-col gap-1 rounded-xl border border-border bg-surface-hover p-1 shadow-sm', className)}
      {...props}
    >
      {children}
    </section>
  );
}

export function FrameHeader({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex min-w-0 items-start justify-between gap-3 px-3 py-2.5 sm:px-4', className)} {...props}>
      {children}
    </div>
  );
}

export function FrameTitle({ className, children, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={cn('min-w-0 text-[13px] font-semibold leading-5 text-ink', className)} {...props}>
      {children}
    </h2>
  );
}

export function FrameDescription({ className, children, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn('mt-0.5 text-[11.5px] leading-4 text-ink-muted', className)} {...props}>
      {children}
    </p>
  );
}

export function FramePanel({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('min-w-0 rounded-lg border border-border bg-surface', className)} {...props}>
      {children}
    </div>
  );
}
