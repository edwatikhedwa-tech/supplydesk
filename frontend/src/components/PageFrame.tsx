import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/utils';

export function PageFrame({ children, width = 'wide', className, ...props }: { children: ReactNode; width?: 'wide' | 'content' | 'narrow'; className?: string } & HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('sd-page', className)} {...props}><div className={cn('sd-page-inner', width === 'content' && 'sd-page-inner-content', width === 'narrow' && 'sd-page-inner-narrow')}>{children}</div></div>;
}

export function PageIntro({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: ReactNode; actions?: ReactNode }) {
  return <div className="sd-page-intro"><div className="min-w-0"><div className="sd-eyebrow">{eyebrow || 'Рабочее пространство'}</div><h1 className="sd-page-title sd-shimmer-heading">{title}</h1>{description && <p className="sd-page-description">{description}</p>}</div>{actions && <div className="sd-page-actions">{actions}</div>}</div>;
}
