import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select';
import { cn } from '../../lib/cn';
import type { ConversationStatus } from '../../lib/types';

/**
 * These are operator workflow states for a supplier conversation. They must
 * not be confused with delivery states such as "Есть ответ" / "Ждём ответа".
 */
const LABEL: Record<ConversationStatus | 'none', string> = {
  none: 'Без статуса',
  in_progress: 'В работе',
  deferred: 'Отложено',
  rejected: 'Отклонено',
};
const STATUS_SURFACE_CLASS: Record<ConversationStatus | 'none', string> = {
  none: 'border-border-strong bg-surface-hover text-ink-muted hover:bg-surface-hover',
  // Green is reserved for the factual delivery state "Есть ответ".
  // The operator's next action should be visually distinct from that fact.
  in_progress: 'border-accent-border bg-accent-subtle text-accent hover:bg-accent-subtle/80',
  deferred: 'border-warning-border bg-warning-subtle text-warning hover:bg-warning-subtle/80',
  rejected: 'border-danger-border bg-danger-subtle text-danger hover:bg-danger-subtle/80',
};
const ORDER: (ConversationStatus | 'none')[] = ['none', 'in_progress', 'deferred', 'rejected'];

function StatusPill({ status }: { status: ConversationStatus | 'none' }) {
  return <span className={cn('inline-flex h-6 min-w-24 shrink-0 items-center justify-center rounded-md border px-2 text-[10px] font-medium leading-none whitespace-nowrap', STATUS_SURFACE_CLASS[status])}>{LABEL[status]}</span>;
}

/**
 * ReUI's c-select-19 composition, adapted to SupplyDesk's existing Radix
 * Select and status vocabulary: one fully tinted semantic trigger instead of
 * an outlined control that contains a second visual badge. The option list
 * uses the same status surfaces.
 */
export function ConversationStatusSelect({
 value,
 onChange,
 size = 'default',
  showLabel = true,
 ariaLabel,
 onClick,
}: {
  value: ConversationStatus | null;
  onChange: (v: ConversationStatus | null) => void;
  size?: 'sm' | 'default';
  showLabel?: boolean;
  ariaLabel: string;
  onClick?: (e: React.MouseEvent) => void;
}) {
  const key = value ?? 'none';
  return (
    <Select value={key} onValueChange={(v) => onChange(v === 'none' ? null : (v as ConversationStatus))}>
      <SelectTrigger
        size={size}
        aria-label={ariaLabel}
        onClick={onClick}
        className={cn(
          'px-2.5 shadow-none',
          STATUS_SURFACE_CLASS[key],
          size === 'sm' && showLabel
            ? 'min-w-[152px] gap-1.5 text-[11px]'
            : size === 'sm'
              ? 'h-8 w-[116px] shrink-0 justify-between gap-1 rounded-[10px] px-2 text-[11px]'
              : 'h-8 w-[176px] rounded-[10px] gap-1.5 text-sm',
        )}
      >
        <span className="flex min-w-0 items-center gap-1.5">
          {showLabel && <span className="shrink-0 font-medium">Статус:</span>}
          <SelectValue>
            <span className="truncate font-medium">{LABEL[key]}</span>
          </SelectValue>
        </span>
      </SelectTrigger>
      <SelectContent
        align={size === 'sm' && !showLabel ? 'end' : 'start'}
        className={size === 'sm' && !showLabel ? 'min-w-[132px]' : undefined}
      >
        {ORDER.map((k) => (
          <SelectItem key={k} value={k}>
            <StatusPill status={k} />
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
