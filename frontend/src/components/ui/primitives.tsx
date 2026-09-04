import { forwardRef, useId, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import type { LucideIcon } from 'lucide-react';
import { AlertTriangle, ChevronDown, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const CONTROL_BASE = 'w-full rounded-lg border border-ink-200 bg-white text-sm text-ink-900 outline-none transition-colors placeholder:text-ink-400 focus:border-accent-400 focus:ring-2 focus:ring-accent-100 disabled:cursor-not-allowed disabled:bg-ink-50 disabled:text-ink-400';

export interface FieldProps {
  label?: ReactNode;
  hint?: string;
  error?: string;
  id?: string;
  className?: string;
}

function FieldMessage({ id, hint, error }: { id?: string; hint?: string; error?: string }) {
  if (error) return <p id={id} role="alert" className="mt-1.5 text-xs font-medium text-rose-700">{error}</p>;
  if (hint) return <p id={id} className="mt-1.5 text-xs text-ink-500">{hint}</p>;
  return null;
}

/** SupplyDesk-only field composition; the canonical Input primitive lives in input.tsx. */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & FieldProps>(function Textarea(
  { label, hint, error, id, className, ...props },
  ref,
) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const messageId = hint || error ? `${controlId}-message` : undefined;
  return (
    <div className="min-w-0">
      {label && <label htmlFor={controlId} className="mb-1.5 block text-xs font-semibold text-ink-700">{label}</label>}
      <textarea
        ref={ref}
        id={controlId}
        aria-invalid={error ? true : undefined}
        aria-describedby={messageId}
        className={cn(CONTROL_BASE, 'min-h-24 resize-y px-3 py-2.5 leading-6', error && 'border-rose-300 focus:border-rose-400 focus:ring-rose-100', className)}
        {...props}
      />
      <FieldMessage id={messageId} hint={hint} error={error} />
    </div>
  );
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & FieldProps>(function Select(
  { label, hint, error, id, className, children, ...props },
  ref,
) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const messageId = hint || error ? `${controlId}-message` : undefined;
  return (
    <div className="min-w-0">
      {label && <label htmlFor={controlId} className="mb-1.5 block text-xs font-semibold text-ink-700">{label}</label>}
      <div className="relative">
        <select
          ref={ref}
          id={controlId}
          aria-invalid={error ? true : undefined}
          aria-describedby={messageId}
          className={cn(CONTROL_BASE, 'h-10 appearance-none px-3 pr-9', error && 'border-rose-300 focus:border-rose-400 focus:ring-rose-100', className)}
          {...props}
        >
          {children}
        </select>
        <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
      </div>
      <FieldMessage id={messageId} hint={hint} error={error} />
    </div>
  );
});

interface ChoiceProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
  description?: string;
}

/** Unused product controls kept local until their first real consumer needs a shadcn migration. */
export function Radio({ label, description, className, ...props }: ChoiceProps) {
  return (
    <label className={cn('group inline-flex min-h-10 cursor-pointer items-start gap-2.5 text-sm text-ink-700', className)}>
      <input {...props} type="radio" className="peer sr-only" />
      <span aria-hidden="true" className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-ink-300 bg-white transition peer-checked:border-accent-600 peer-focus-visible:ring-2 peer-focus-visible:ring-accent-200 peer-disabled:cursor-not-allowed peer-disabled:opacity-50">
        <span className="h-2 w-2 rounded-full bg-accent-600 opacity-0 peer-checked:opacity-100" />
      </span>
      <span className="min-w-0"><span className="block font-medium group-hover:text-ink-900">{label}</span>{description && <span className="mt-0.5 block text-xs text-ink-500">{description}</span>}</span>
    </label>
  );
}

export function Switch({ label, description, className, ...props }: ChoiceProps) {
  return (
    <label className={cn('group inline-flex min-h-10 cursor-pointer items-start gap-3 text-sm text-ink-700', className)}>
      <input {...props} type="checkbox" role="switch" className="peer sr-only" />
      <span aria-hidden="true" className="relative mt-0.5 h-5 w-9 shrink-0 rounded-full bg-ink-300 transition peer-checked:bg-accent-600 peer-focus-visible:ring-2 peer-focus-visible:ring-accent-200 peer-disabled:cursor-not-allowed peer-disabled:opacity-50"><span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform peer-checked:translate-x-4" /></span>
      <span className="min-w-0"><span className="block font-medium group-hover:text-ink-900">{label}</span>{description && <span className="mt-0.5 block text-xs text-ink-500">{description}</span>}</span>
    </label>
  );
}

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
}

export function Card({ className, interactive = false, ...props }: CardProps) {
  return <div className={cn('sd-card', interactive && 'sd-card-interactive', className)} {...props} />;
}

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-3 px-6 py-16 text-center', className)}>
      {Icon && <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-ink-200 bg-ink-50 text-ink-400"><Icon size={21} aria-hidden="true" /></div>}
      <h2 className="text-base font-semibold text-ink-900">{title}</h2>
      {description && <p className="max-w-sm text-sm leading-6 text-ink-500">{description}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  message: string;
  retryLabel?: string;
  onRetry?: () => void;
  retrying?: boolean;
  className?: string;
}

export function ErrorState({ title = 'Не удалось загрузить данные', message, retryLabel = 'Повторить', onRetry, retrying = false, className }: ErrorStateProps) {
  return (
    <div className={cn('flex min-h-[320px] items-center justify-center px-6 py-10', className)}>
      <div role="alert" className="w-full max-w-md rounded-xl border border-rose-200 bg-white p-7 text-center shadow-panel">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-600"><AlertTriangle size={21} aria-hidden="true" /></div>
        <h1 className="mt-5 text-lg font-bold text-ink-900">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-ink-500">{message}</p>
        {onRetry && <button type="button" onClick={onRetry} disabled={retrying} className="mt-6 inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 py-2.5 text-sm font-semibold text-white shadow-soft transition hover:bg-accent-700 disabled:cursor-wait disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2">{retrying && <Loader2 size={15} className="animate-spin" />}{retrying ? 'Загружаем…' : retryLabel}</button>}
      </div>
    </div>
  );
}

export function LoadingState({ label = 'Загрузка…', className }: { label?: string; className?: string }) {
  return <div role="status" aria-busy="true" aria-label={label} className={cn('flex min-h-[320px] items-center justify-center px-6 py-10 text-sm text-ink-500', className)}><Loader2 size={16} className="mr-2 animate-spin text-accent-600" />{label}</div>;
}

export function Toast({ tone = 'neutral', children, className }: { tone?: 'neutral' | 'success' | 'warning' | 'danger'; children: ReactNode; className?: string }) {
  const toneClasses = { neutral: 'border-ink-200 bg-white text-ink-700', success: 'border-emerald-200 bg-emerald-50 text-emerald-800', warning: 'border-amber-200 bg-amber-50 text-amber-900', danger: 'border-rose-200 bg-rose-50 text-rose-800' };
  return <div role="status" aria-live="polite" className={cn('rounded-lg border px-3 py-2.5 text-xs font-semibold shadow-soft', toneClasses[tone], className)}>{children}</div>;
}

export function TableShell({ children, className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('sd-table-shell', className)} {...props}>{children}</div>;
}
