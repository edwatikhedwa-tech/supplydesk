import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'link';
export type ButtonSize = 'sm' | 'md';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-accent-600 text-white shadow-soft hover:bg-accent-700 focus-visible:ring-accent-500',
  secondary: 'border border-ink-200 bg-white text-ink-700 shadow-soft hover:border-ink-300 hover:bg-ink-50 focus-visible:ring-accent-500',
  ghost: 'text-ink-600 hover:bg-ink-100 hover:text-ink-900 focus-visible:ring-accent-400',
  danger: 'bg-rose-600 text-white shadow-soft hover:bg-rose-700 focus-visible:ring-rose-500',
  link: 'text-accent-700 hover:bg-accent-50 hover:text-accent-800 focus-visible:ring-accent-400',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'min-h-9 px-3 text-xs',
  md: 'min-h-10 px-4 text-sm',
};

/** A small product-level action primitive; it intentionally does not add a
 * component library dependency and keeps action hierarchy explicit. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = 'secondary', size = 'md', type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        'inline-flex shrink-0 items-center justify-center gap-2 rounded-lg font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    />
  );
});
