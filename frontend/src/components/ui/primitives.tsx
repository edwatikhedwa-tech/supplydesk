import { forwardRef, useEffect, useId, useRef, useState, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import type { LucideIcon } from 'lucide-react';
import { AlertTriangle, Check, ChevronDown, Loader2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useDialogFocus } from '@/hooks/useDialogFocus';

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

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & FieldProps>(function Input(
  { label, hint, error, id, className, ...props },
  ref,
) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const messageId = hint || error ? `${controlId}-message` : undefined;
  return (
    <div className="min-w-0">
      {label && <label htmlFor={controlId} className="mb-1.5 block text-xs font-semibold text-ink-700">{label}</label>}
      <input
        ref={ref}
        id={controlId}
        aria-invalid={error ? true : undefined}
        aria-describedby={messageId}
        className={cn(CONTROL_BASE, 'h-10 px-3', error && 'border-rose-300 focus:border-rose-400 focus:ring-rose-100', className)}
        {...props}
      />
      <FieldMessage id={messageId} hint={hint} error={error} />
    </div>
  );
});

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

export function Checkbox({ label, description, className, ...props }: ChoiceProps) {
  return (
    <label className={cn('group inline-flex min-h-10 cursor-pointer items-start gap-2.5 text-sm text-ink-700', className)}>
      <input {...props} type="checkbox" className="peer sr-only" />
      <span aria-hidden="true" className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-ink-300 bg-white text-white transition peer-checked:border-accent-600 peer-checked:bg-accent-600 peer-focus-visible:ring-2 peer-focus-visible:ring-accent-200 peer-disabled:cursor-not-allowed peer-disabled:opacity-50">
        <Check className="h-3 w-3 opacity-0 peer-checked:opacity-100" />
      </span>
      <span className="min-w-0">
        <span className="block font-medium group-hover:text-ink-900">{label}</span>
        {description && <span className="mt-0.5 block text-xs text-ink-500">{description}</span>}
      </span>
    </label>
  );
}

export function Radio({ label, description, className, ...props }: ChoiceProps) {
  return (
    <label className={cn('group inline-flex min-h-10 cursor-pointer items-start gap-2.5 text-sm text-ink-700', className)}>
      <input {...props} type="radio" className="peer sr-only" />
      <span aria-hidden="true" className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-ink-300 bg-white transition peer-checked:border-accent-600 peer-focus-visible:ring-2 peer-focus-visible:ring-accent-200 peer-disabled:cursor-not-allowed peer-disabled:opacity-50">
        <span className="h-2 w-2 rounded-full bg-accent-600 opacity-0 peer-checked:opacity-100" />
      </span>
      <span className="min-w-0">
        <span className="block font-medium group-hover:text-ink-900">{label}</span>
        {description && <span className="mt-0.5 block text-xs text-ink-500">{description}</span>}
      </span>
    </label>
  );
}

export function Switch({ label, description, className, ...props }: ChoiceProps) {
  return (
    <label className={cn('group inline-flex min-h-10 cursor-pointer items-start gap-3 text-sm text-ink-700', className)}>
      <input {...props} type="checkbox" role="switch" className="peer sr-only" />
      <span aria-hidden="true" className="relative mt-0.5 h-5 w-9 shrink-0 rounded-full bg-ink-300 transition peer-checked:bg-accent-600 peer-focus-visible:ring-2 peer-focus-visible:ring-accent-200 peer-disabled:cursor-not-allowed peer-disabled:opacity-50">
        <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform peer-checked:translate-x-4" />
      </span>
      <span className="min-w-0">
        <span className="block font-medium group-hover:text-ink-900">{label}</span>
        {description && <span className="mt-0.5 block text-xs text-ink-500">{description}</span>}
      </span>
    </label>
  );
}

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
}

export function Card({ className, interactive = false, ...props }: CardProps) {
  return <div className={cn('sd-card', interactive && 'sd-card-interactive', className)} {...props} />;
}

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={cn('sd-skeleton', className)} {...props} />;
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

export interface DropdownMenuItem {
  id: string;
  label: string;
  disabled?: boolean;
}

export function DropdownMenu({ label, items, value, onSelect, align = 'right' }: { label: string; items: DropdownMenuItem[]; value?: string; onSelect: (id: string) => void; align?: 'left' | 'right' }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const selected = items.find((item) => item.id === value);
  useEffect(() => {
    if (!open) return undefined;
    const handlePointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !containerRef.current?.contains(event.target)) setOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => { document.removeEventListener('pointerdown', handlePointerDown); document.removeEventListener('keydown', handleKeyDown); };
  }, [open]);
  return (
    <div ref={containerRef} className="relative">
      <button type="button" aria-haspopup="menu" aria-expanded={open} aria-controls={menuId} onClick={() => setOpen((current) => !current)} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-ink-200 bg-white px-3 text-xs font-semibold text-ink-700 shadow-soft transition hover:border-ink-300 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-200">
        {selected?.label ?? label}<ChevronDown className={cn('h-3.5 w-3.5 text-ink-400 transition-transform', open && 'rotate-180')} aria-hidden="true" />
      </button>
      {open && <div id={menuId} role="menu" className={cn('absolute top-11 z-40 min-w-44 rounded-lg border border-ink-200 bg-white p-1 shadow-float', align === 'right' ? 'right-0' : 'left-0')}>
        {items.map((item) => <button key={item.id} type="button" role="menuitem" disabled={item.disabled} onClick={() => { onSelect(item.id); setOpen(false); }} className={cn('flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-xs transition hover:bg-ink-50 disabled:cursor-not-allowed disabled:opacity-50', item.id === value ? 'font-semibold text-accent-700' : 'text-ink-700')}><span>{item.label}</span>{item.id === value && <Check className="h-3.5 w-3.5" aria-hidden="true" />}</button>)}
      </div>}
    </div>
  );
}

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  const tooltipId = useId();
  return <span className="group relative inline-flex" aria-describedby={tooltipId}>{children}<span id={tooltipId} role="tooltip" className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 w-max max-w-56 -translate-x-1/2 rounded-md bg-ink-900 px-2.5 py-1.5 text-2xs font-medium text-white opacity-0 shadow-float transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">{label}</span></span>;
}

export function Dialog({ open, onClose, title, description, children, actions, size = 'md' }: { open: boolean; onClose: () => void; title: string; description?: string; children?: ReactNode; actions?: ReactNode; size?: 'sm' | 'md' | 'lg' }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useDialogFocus(dialogRef, closeRef, onClose, open);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-ink-900/25 p-0 backdrop-blur-[2px] sm:items-center sm:p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="sd-dialog-title" aria-describedby={description ? 'sd-dialog-description' : undefined} tabIndex={-1} className={cn('max-h-[min(720px,calc(100vh-32px))] w-full overflow-y-auto rounded-t-xl border border-ink-200 bg-white shadow-float sm:rounded-xl', size === 'sm' ? 'max-w-sm' : size === 'lg' ? 'max-w-2xl' : 'max-w-lg')}>
        <div className="flex items-start justify-between gap-4 border-b border-ink-100 px-5 py-4">
          <div className="min-w-0"><h2 id="sd-dialog-title" className="text-base font-bold text-ink-900">{title}</h2>{description && <p id="sd-dialog-description" className="mt-1 text-xs leading-5 text-ink-500">{description}</p>}</div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Закрыть" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ink-400 transition hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"><X size={17} aria-hidden="true" /></button>
        </div>
        {children && <div className="p-5">{children}</div>}
        {actions && <div className="flex flex-col-reverse gap-2 border-t border-ink-100 bg-ink-50 px-5 py-3 sm:flex-row sm:justify-end">{actions}</div>}
      </div>
    </div>
  );
}

export function Sheet({ open, onClose, title, description, children, side = 'right' }: { open: boolean; onClose: () => void; title: string; description?: string; children?: ReactNode; side?: 'left' | 'right' }) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useDialogFocus(sheetRef, closeRef, onClose, open);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] bg-ink-900/25 backdrop-blur-[2px]" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside ref={sheetRef} role="dialog" aria-modal="true" aria-labelledby="sd-sheet-title" tabIndex={-1} className={cn('absolute inset-y-0 flex w-full max-w-xl flex-col bg-white shadow-float', side === 'right' ? 'right-0' : 'left-0')}>
        <div className="flex items-start justify-between gap-4 border-b border-ink-100 px-5 py-4"><div className="min-w-0"><h2 id="sd-sheet-title" className="text-base font-bold text-ink-900">{title}</h2>{description && <p className="mt-1 text-xs leading-5 text-ink-500">{description}</p>}</div><button ref={closeRef} type="button" onClick={onClose} aria-label="Закрыть" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ink-400 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"><X size={17} aria-hidden="true" /></button></div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
      </aside>
    </div>
  );
}

export function Tabs({ items, value, onChange, label = 'Разделы' }: { items: { id: string; label: string; count?: number | string }[]; value: string; onChange: (id: string) => void; label?: string }) {
  return <div role="tablist" aria-label={label} className="flex min-w-0 items-center gap-1 overflow-x-auto">{items.map((item) => <button key={item.id} type="button" role="tab" aria-selected={item.id === value} onClick={() => onChange(item.id)} className={cn('relative inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-lg px-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-200', item.id === value ? 'bg-ink-100 text-ink-900' : 'text-ink-500 hover:bg-ink-50 hover:text-ink-800')}>{item.label}{item.count != null && <span className={cn('text-xs tabular-nums', item.id === value ? 'text-ink-500' : 'text-ink-400')}>{item.count}</span>}</button>)}</div>;
}

export function Toast({ tone = 'neutral', children, className }: { tone?: 'neutral' | 'success' | 'warning' | 'danger'; children: ReactNode; className?: string }) {
  const toneClasses = { neutral: 'border-ink-200 bg-white text-ink-700', success: 'border-emerald-200 bg-emerald-50 text-emerald-800', warning: 'border-amber-200 bg-amber-50 text-amber-900', danger: 'border-rose-200 bg-rose-50 text-rose-800' };
  return <div role="status" aria-live="polite" className={cn('rounded-lg border px-3 py-2.5 text-xs font-semibold shadow-soft', toneClasses[tone], className)}>{children}</div>;
}

export function TableShell({ children, className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('sd-table-shell', className)} {...props}>{children}</div>;
}
