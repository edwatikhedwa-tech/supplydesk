import type { InputHTMLAttributes } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from './input';

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  icon?: LucideIcon;
  error?: string;
}

export function TextField({ label, icon: Icon, error, id, className, ...props }: TextFieldProps) {
  const describedBy = error && id ? `${id}-error` : undefined;
  return (
    <div className={cn('relative', className)}>
      <label htmlFor={id} className="sr-only">{label}</label>
      {Icon && <Icon size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" aria-hidden={true} />}
      <Input
        id={id}
        aria-label={label}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={cn(
          'h-10 w-full rounded-lg border border-ink-200 bg-white text-sm text-ink-900 outline-none transition-colors placeholder:text-ink-400 focus:border-accent-400 focus:ring-2 focus:ring-accent-100',
          Icon ? 'pl-10' : 'px-3',
          error && 'border-rose-300 focus:border-rose-400 focus:ring-rose-100',
        )}
        {...props}
      />
      {error && <p id={describedBy} role="alert" className="mt-1 text-xs text-rose-700">{error}</p>}
    </div>
  );
}
