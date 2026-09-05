import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <Icon size={22} strokeWidth={1.5} className="text-ink-faint" />
      <p className="text-[13px] font-medium text-ink-soft">{title}</p>
      {description && <p className="max-w-[36ch] text-[12.5px] text-ink-muted">{description}</p>}
      {action}
    </div>
  );
}
