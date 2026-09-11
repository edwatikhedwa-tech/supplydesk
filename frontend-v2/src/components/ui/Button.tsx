import clsx from 'clsx';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'sm' | 'md';

const variantClasses: Record<Variant, string> = {
  primary: 'bg-accent text-white hover:bg-accent-hover border border-transparent shadow-sm',
  secondary: 'bg-surface text-ink border border-border-strong hover:bg-surface-hover',
  // A row this button sits in often has its own hover:bg-surface-hover -- if
  // the button used the same tint, hovering it looked identical to just
  // hovering the row, so it read as "nothing is highlighted". Ghost buttons
  // shift to the accent tint plus a real border instead, so the button
  // itself is unmistakably the hovered target.
  ghost: 'bg-transparent text-ink-soft border border-transparent hover:border-accent-border hover:bg-accent-subtle hover:text-accent',
};

const sizeClasses: Record<Size, string> = {
  // ReUI-style action sizing: the compact action still has a stable 32 px
  // hit area, matching Select and other controls across the workspace.
  sm: 'h-8 px-3 text-[12px] gap-1.5',
  md: 'h-9 px-3.5 text-[13px] gap-1.5',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  icon,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
}) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center rounded-[10px] font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border disabled:opacity-50 disabled:pointer-events-none',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}
