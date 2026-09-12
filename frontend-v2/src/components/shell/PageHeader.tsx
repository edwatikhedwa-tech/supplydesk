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
    <div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-4 pb-3 sm:gap-4 sm:px-6 sm:pt-5">
      <div className="min-w-0">
        <div className="flex items-center gap-2" aria-label={`Раздел: ${title}`}>
          <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
          <h1 className="font-display text-[19px] font-semibold leading-tight text-ink">{title}</h1>
          <div role="separator" aria-hidden="true" className="ml-2 h-px min-w-8 max-w-24 flex-1 bg-border" />
        </div>
        {description && <p className="mt-1 text-[12px] text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
