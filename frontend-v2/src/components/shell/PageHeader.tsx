import clsx from 'clsx';
import type { ReactNode } from 'react';

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className={clsx('flex flex-wrap items-start justify-between gap-3 px-4 pt-4 sm:gap-4 sm:px-6 sm:pt-6', description ? 'pb-4' : 'pb-3')}>
      <div className="min-w-0">
        <h1 className="font-display text-[19px] font-semibold leading-tight text-ink">{title}</h1>
        {description && <p className="mt-0.5 text-[12.5px] text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
